# -*- coding: utf-8 -*-
"""版本列表获取源：npm registry / PyPI / GitHub Releases / Maven Central。"""
from __future__ import annotations

import re
from typing import Any

import httpx

TIMEOUT = 8.0
UA = {"User-Agent": "zhuang-le-ma/1.0 (+https://github.com/)"}

try:  # 可选的 GitHub Token，避免匿名 60 次/小时限流
    from .config import settings as _s

    GH_TOKEN = _s.GITHUB_TOKEN
except Exception:  # pragma: no cover
    GH_TOKEN = ""


VERSION_RE = re.compile(r"^\d+(\.\d+){0,3}$")


def _clean_versions(raw: list[str], limit: int = 30) -> list[str]:
    """只保留纯数字版本号（去掉预发布与怪异 tag），按语义倒序。"""
    stable = []
    for v in raw:
        v = (v or "").strip()
        if not v:
            continue
        # 去掉 v / go / mysql- / REL_ 之类的前缀
        v = re.sub(r"^\D*(?=\d)", "", v).replace("_", ".").strip()
        v = v.lstrip("v")
        if not VERSION_RE.match(v):
            continue
        stable.append(v)

    def key(v: str):
        nums = re.findall(r"\d+", v)
        return tuple(int(n) for n in nums[:4]) if nums else (0,)

    stable = sorted(set(stable), key=key, reverse=True)
    return stable[:limit]


async def from_npm(pkg: str) -> list[str]:
    url = f"https://registry.npmjs.org/{pkg}"
    async with httpx.AsyncClient(timeout=TIMEOUT, headers=UA, follow_redirects=True) as c:
        r = await c.get(url)
        r.raise_for_status()
        data = r.json()
    versions = list(data.get("versions", {}).keys())
    return _clean_versions(versions)


async def from_pypi(pkg: str) -> list[str]:
    url = f"https://pypi.org/pypi/{pkg}/json"
    async with httpx.AsyncClient(timeout=TIMEOUT, headers=UA, follow_redirects=True) as c:
        r = await c.get(url)
        r.raise_for_status()
        data = r.json()
    versions = list(data.get("releases", {}).keys())
    return _clean_versions(versions)


async def from_github(repo: str, match: str | None = None) -> list[str]:
    """match：可选的 tag 过滤正则（如 MySQL 只要 ^mysql-\\d 而不要 cluster 分支）。"""
    url = f"https://api.github.com/repos/{repo}/releases?per_page=60"
    headers = dict(UA)
    headers["Accept"] = "application/vnd.github+json"
    if GH_TOKEN:
        headers["Authorization"] = f"Bearer {GH_TOKEN}"

    def _pick(rows: list[dict]) -> list[str]:
        out = []
        for rel in rows:
            tag = rel.get("tag_name") or rel.get("name") or ""
            if match and not re.search(match, tag):
                continue
            out.append(tag)
        return _clean_versions(out)

    async with httpx.AsyncClient(timeout=TIMEOUT, headers=headers, follow_redirects=True) as c:
        r = await c.get(url)
        data = r.json() if r.status_code == 200 else []
        names = _pick(data) if isinstance(data, list) else []
        if not names:
            # 没有 releases（很多项目只打 tag）就退回 tags
            r2 = await c.get(f"https://api.github.com/repos/{repo}/tags?per_page=60")
            r2.raise_for_status()
            tags = r2.json() if isinstance(r2.json(), list) else []
            names = _pick(tags)
    return names


async def from_maven(gav: str) -> list[str]:
    if ":" not in gav:
        return []
    group, artifact = gav.split(":", 1)
    url = "https://search.maven.org/solrsearch/select"
    params = {"q": f'g:"{group}" AND a:"{artifact}"', "core": "gav", "rows": "30", "wt": "json"}
    async with httpx.AsyncClient(timeout=TIMEOUT, headers=UA, follow_redirects=True) as c:
        r = await c.get(url, params=params)
        r.raise_for_status()
        data = r.json()
    docs = data.get("response", {}).get("docs", [])
    return _clean_versions([d.get("v", "") for d in docs])


async def fetch_versions(source_kind: str, source_key: str,
                         match: str | None = None) -> tuple[list[str], str]:
    """返回 (版本列表, 实际来源)。出错返回 ([], source_kind)。"""
    if not source_key:
        return [], source_kind
    try:
        if source_kind == "npm":
            return await from_npm(source_key), "npm"
        if source_kind == "pypi":
            return await from_pypi(source_key), "pypi"
        if source_kind == "github":
            return await from_github(source_key, match), "github"
        if source_kind == "maven":
            return await from_maven(source_key), "maven"
    except Exception:
        return [], source_kind
    return [], source_kind


async def probe_software(pkg: str) -> dict[str, Any]:
    """未知软件时，按 npm -> pypi -> github 顺序探测可用源。"""
    for kind, fn in (("npm", from_npm), ("pypi", from_pypi)):
        try:
            vs = await fn(pkg)
            if vs:
                return {"source_kind": kind, "source_key": pkg, "versions": vs}
        except Exception:
            continue
    return {}
