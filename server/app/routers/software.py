# -*- coding: utf-8 -*-
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas import ResolveIn
from ..service import get_versions, resolve_software, software_to_dict
from ..models import Software, Version

router = APIRouter(prefix="/api", tags=["software"])


@router.get("/softwares")
async def list_softwares(q: str = "", limit: int = 50, db: Session = Depends(get_db)):
    query = db.query(Software)
    if q:
        like = f"%{q.lower()}%"
        query = query.filter(
            Software.name.ilike(like) | Software.slug.ilike(like) | Software.aliases.ilike(like)
        )
    rows = query.order_by(Software.id).limit(limit).all()
    return {"items": [software_to_dict(s) for s in rows]}


@router.post("/resolve")
async def resolve(payload: ResolveIn, db: Session = Depends(get_db)):
    sw = await resolve_software(db, payload.query)
    if not sw:
        raise HTTPException(404, "没能识别出你要装啥，换个说法试试？")
    return {"software": software_to_dict(sw)}


@router.get("/softwares/{key}/versions")
async def versions(key: str, refresh: bool = Query(False),
                   platform: str = Query("", description="windows 时以 winget 可装版本为准"),
                   db: Session = Depends(get_db)):
    from ..service import find_software
    sw = find_software(db, key)
    if not sw:
        sw = await resolve_software(db, key)
    if not sw:
        raise HTTPException(404, "没找到这个软件")
    vs, source = await get_versions(db, sw, refresh=refresh, platform=platform or None)
    rows = {v.version: v for v in db.query(Version).filter(Version.software_id == sw.id).all()}
    return {
        "software": software_to_dict(sw),
        "latest": vs[0] if vs else None,
        "source": source,
        "versions": [
            {"version": v, "is_latest": int(rows.get(v).is_latest) if rows.get(v) else 0}
            for v in vs
        ],
    }
