# -*- coding: utf-8 -*-
"""业务层：软件解析 / 版本获取 / 方案生成与缓存。"""
from __future__ import annotations

import asyncio
import logging
import re

from sqlalchemy import func
from sqlalchemy.orm import Session

from . import planner, version_sources
from .catalog import find_preset
from .models import Feedback, Plan, Software, StatEvent, Version

logger = logging.getLogger("anlema.service")

PLATFORMS = ("windows", "macos", "linux")


def slugify(name: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", (name or "").strip().lower()).strip("-")
    return s or "unknown"


def normalize_platform(p: str | None) -> str:
    p = (p or "").strip().lower()
    if p in PLATFORMS:
        return p
    mapping = {
        "win": "windows", "windows": "windows", "win32": "windows", "win64": "windows",
        "mac": "macos", "macos": "macos", "darwin": "macos", "osx": "macos", "mac os x": "macos",
        "linux": "linux", "ubuntu": "linux", "debian": "linux", "centos": "linux",
    }
    return mapping.get(p, "")


def software_to_dict(s: Software) -> dict:
    return {
        "id": s.id,
        "name": s.name,
        "slug": s.slug,
        "aliases": s.aliases or "",
        "category": s.category,
        "icon": s.icon,
        "tagline": s.tagline,
        "official_url": s.official_url,
        "docs_url": s.docs_url,
        "source_kind": s.source_kind,
        "source_key": s.source_key,
        "install_type": s.install_type,
    }


def find_software(db: Session, key: str) -> Software | None:
    if not key:
        return None
    k = key.strip()
    if k.isdigit():
        return db.get(Software, int(k))
    s = db.query(Software).filter(func.lower(Software.slug) == k.lower()).first()
    if s:
        return s
    s = db.query(Software).filter(func.lower(Software.name) == k.lower()).first()
    if s:
        return s
    return None


def create_software(db: Session, data: dict) -> Software:
    name = (data.get("name") or "").strip()
    slug = (data.get("slug") or slugify(name)).strip().lower()
    exists = db.query(Software).filter(Software.slug == slug).first()
    if exists:
        return exists
    s = Software(
        name=name,
        slug=slug,
        aliases=data.get("aliases", ""),
        category=data.get("category", "other"),
        official_url=data.get("official_url", ""),
        docs_url=data.get("docs_url", ""),
        icon=data.get("icon", "📦"),
        tagline=data.get("tagline", ""),
        source_kind=data.get("source_kind", "manual"),
        source_key=data.get("source_key", ""),
        install_type=data.get("install_type", "script"),
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


async def resolve_software(db: Session, query: str) -> Software | None:
    """一句话 → 软件实体。策略：库内匹配 → 预置目录 → 在线探测 → AI。"""
    q = (query or "").strip()
    if not q:
        return None

    hit = find_software(db, q)
    if hit:
        return hit

    # 库内模糊匹配（含别名）
    like = f"%{q.lower()}%"
    cands = db.query(Software).filter(
        func.lower(Software.name).like(like) | func.lower(Software.aliases).like(like)
    ).all()
    if cands:
        cands.sort(key=lambda s: len(s.name))
        return cands[0]

    preset = find_preset(q)
    if preset:
        return create_software(db, preset)

    # 在线探测 npm / pypi
    probe_key = re.sub(r"[^a-zA-Z0-9._\-]", "", q.strip().lower())
    if probe_key:
        probed = await version_sources.probe_software(probe_key)
        if probed:
            return create_software(db, {
                "name": q.strip(),
                "slug": slugify(probe_key),
                "source_kind": probed["source_kind"],
                "source_key": probed["source_key"],
                "category": "other",
                "install_type": "script",
            })

    ai = await planner.ai_resolve(q)
    if ai and ai.get("name"):
        return create_software(db, ai)
    if ai is None and q:
        # AI 不可用也别让用户空手而归
        return create_software(db, {"name": q.strip(), "slug": slugify(q), "category": "other"})
    return None


def _save_versions(db: Session, sw: Software, versions: list[str], source: str) -> None:
    db.query(Version).filter(Version.software_id == sw.id).update({Version.is_latest: 0})
    for i, v in enumerate(versions):
        row = db.query(Version).filter(
            Version.software_id == sw.id, Version.version == v
        ).first()
        if not row:
            row = Version(software_id=sw.id, version=v, source=source)
            db.add(row)
        row.source = source
        row.is_latest = 1 if i == 0 else 0
    db.commit()


async def get_versions(db: Session, sw: Software, refresh: bool = False,
                       platform: str | None = None) -> tuple[list[str], str]:
    """缓存 → 包管理器（Windows 的 winget）→ 在线源 → 预置兜底 → AI。

    platform="windows" 时以 winget 仓库为准：它没保留的老版本不能选，
    否则脚本里 `winget install --version 1.24.0` 一定失败。
    返回 (版本列表, 来源)。
    """
    preset = find_preset(sw.name)
    if platform == "windows":
        wid = ((preset or {}).get("install") or {}).get("winget")
        if wid:
            from . import pkg_versions

            wv = await pkg_versions.winget_versions(wid, refresh=refresh)
            if wv:
                _save_versions(db, sw, wv, "winget")
                return wv, "winget"

    cached = db.query(Version).filter(Version.software_id == sw.id).all()
    if cached and not refresh:
        vs = sorted(cached, key=lambda v: (not v.is_latest, v.version), reverse=False)
        ordered = [v.version for v in sorted(cached, key=lambda v: v.is_latest, reverse=True)]
        # is_latest 优先，其余按 id 倒序
        rest = [v.version for v in sorted(cached, key=lambda v: v.id, reverse=True)]
        result, seen = [], set()
        for v in ordered[:1] + rest:
            if v not in seen:
                seen.add(v)
                result.append(v)
        return result, "cache"

    versions: list[str] = []
    source = "cache"
    if sw.source_kind and sw.source_key:
        match = (preset or {}).get("version_match")
        versions, source = await version_sources.fetch_versions(
            sw.source_kind, sw.source_key, match
        )

    if not versions and preset:
        versions = list(preset.get("fallback_versions") or [])
        source = "preset"

    if not versions:
        versions = await planner.ai_versions(sw.name)
        source = "ai"

    if not versions:
        versions = ["latest"]
        source = "fallback"

    _save_versions(db, sw, versions, source)
    return versions, source


def latest_version(db: Session, sw: Software) -> str | None:
    row = db.query(Version).filter(
        Version.software_id == sw.id, Version.is_latest == 1
    ).first()
    return row.version if row else None


async def _upgrade_in_background(plan_id: int, software: dict, version: str, platform: str) -> None:
    """AI 写好后在后台把模板方案升级成 AI 方案（用户已经拿到模板，不用干等）。"""
    from .database import SessionLocal  # 局部导入，避免循环引用

    db = SessionLocal()
    try:
        # 后台跑，用户不用干等，给足预算（AI 写完整方案实测要 3-6 分钟）
        md, summary, by, _official = await planner.generate_plan_md(
            software, version, platform, timeout=600
        )
        if by != "ai":
            logger.info("后台升级未拿到 AI 方案（来源=%s），保留模板", by)
            return
        p = db.query(Plan).filter(Plan.id == plan_id).first()
        if not p:
            return
        # 用户可能已经手动编辑过，人工改过的方案不覆盖
        if (p.generated_by or "") == "manual":
            logger.info("方案 %s 已被人工编辑，跳过升级", plan_id)
            return
        p.content_md = md
        p.summary = summary
        p.generated_by = "ai"
        db.commit()
        logger.info("后台已把方案 %s 升级为 AI 版（%d 字）", plan_id, len(md))
    except Exception as e:  # noqa: BLE001
        logger.warning("后台升级方案失败：%s", e)
    finally:
        db.close()


async def get_or_create_plan(db: Session, software_key: str, version: str | None,
                             platform: str, force: bool = False,
                             fast: bool = False) -> Plan | None:
    sw = await resolve_software(db, software_key)
    if not sw:
        return None
    platform = normalize_platform(platform) or "windows"

    if not version:
        vs, _ = await get_versions(db, sw)
        version = vs[0] if vs else "latest"

    q = db.query(Plan).filter(
        Plan.software_id == sw.id, Plan.version == version, Plan.platform == platform
    )
    plan = q.first()
    # 模板升级后，旧的 template 方案要重新生成，否则用户一直看到旧脚本
    if plan and not force and not planner.is_stale_template(plan.content_md, plan.generated_by):
        plan.view_count = (plan.view_count or 0) + 1
        db.commit()
        return plan

    # fast 模式：先秒出本地模板给用户，AI 在后台慢慢写，写完自动升级（不让用户干等几分钟）
    if fast:
        md = planner.local_template(software_to_dict(sw), version, platform)
        by = "template"
        summary = planner.summarize(md)
        official = sw.official_url or ""
        if plan:
            plan.content_md = md
            plan.summary = summary
            plan.generated_by = by
            plan.official_url = official or sw.official_url
            plan.view_count = (plan.view_count or 0) + 1
        else:
            plan = Plan(
                software_id=sw.id,
                software_name=sw.name,
                version=version,
                platform=platform,
                title=f"{sw.name} {version} · {platform} 安装方案",
                summary=summary,
                content_md=md,
                official_url=official or sw.official_url,
                generated_by=by,
                view_count=1,
            )
            db.add(plan)
        db.commit()
        db.refresh(plan)
        asyncio.create_task(
            _upgrade_in_background(plan.id, software_to_dict(sw), version, platform)
        )
        return plan

    md, summary, by, official = await planner.generate_plan_md(
        software_to_dict(sw), version, platform
    )
    if plan:
        plan.content_md = md
        plan.summary = summary
        plan.generated_by = by
        plan.official_url = official or sw.official_url
        plan.view_count = (plan.view_count or 0) + 1
    else:
        plan = Plan(
            software_id=sw.id,
            software_name=sw.name,
            version=version,
            platform=platform,
            title=f"{sw.name} {version} · {platform} 安装方案",
            summary=summary,
            content_md=md,
            official_url=official or sw.official_url,
            generated_by=by,
            view_count=1,
        )
        db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan


def record_event(db: Session, software_name: str, version: str, platform: str, event_type: str):
    db.add(StatEvent(
        software_name=software_name, version=version or "",
        platform=platform or "", event_type=event_type,
    ))
    db.commit()
    if event_type in ("valid", "invalid") and software_name:
        logger.info("记录反馈事件 %s %s", software_name, event_type)
    return True
