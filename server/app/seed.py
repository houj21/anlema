# -*- coding: utf-8 -*-
"""初始化数据库 & 预置软件。"""
from .catalog import PRESET
from .database import Base, SessionLocal, engine
from .models import Software, Version
from .service import create_software, slugify


def seed() -> int:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    count = 0
    try:
        for item in PRESET:
            sw = db.query(Software).filter(Software.slug == item["slug"]).first()
            if not sw:
                sw = create_software(db, item)
                count += 1
            else:
                # 目录升级时同步元信息
                for f in ("source_kind", "source_key", "install_type", "official_url",
                          "docs_url", "icon", "tagline", "category", "aliases"):
                    val = item.get(f)
                    if val and getattr(sw, f) != val:
                        setattr(sw, f, val)
            # 预置兜底版本先落库，保证首屏秒开
            if db.query(Version).filter(Version.software_id == sw.id).count() == 0:
                for i, v in enumerate(item.get("fallback_versions") or []):
                    db.add(Version(software_id=sw.id, version=v, is_latest=1 if i == 0 else 0,
                                   source="preset"))
        db.commit()
    finally:
        db.close()
    return count
