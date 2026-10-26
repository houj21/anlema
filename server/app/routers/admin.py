# -*- coding: utf-8 -*-
from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..models import Feedback, Plan, Software, StatEvent
from ..schemas import EventIn, FeedbackIn, FeedbackUpdateIn, LoginIn, PlanUpdateIn, model_to_dict
from ..service import get_or_create_plan, record_event

router = APIRouter(prefix="/api", tags=["admin"])


def require_admin(x_admin_token: str = Header(default="", alias="X-Admin-Token")):
    if not x_admin_token or x_admin_token != settings.admin_token:
        raise HTTPException(401, "口令不对，回去想想（默认口令见 README）")
    return True


@router.post("/admin/login")
async def login(payload: LoginIn):
    if payload.password == settings.ADMIN_PASSWORD and (
        not payload.username or payload.username == settings.ADMIN_USERNAME
    ):
        return {"ok": True, "token": settings.admin_token, "username": settings.ADMIN_USERNAME}
    raise HTTPException(401, "口令不对哦")


@router.get("/admin/check")
async def admin_check(_=Depends(require_admin)):
    return {"ok": True}


# ---------------- 方案管理 ----------------
@router.patch("/admin/plans/{plan_id}")
async def update_plan(plan_id: int, payload: PlanUpdateIn, db: Session = Depends(get_db),
                      _=Depends(require_admin)):
    plan = db.get(Plan, plan_id)
    if not plan:
        raise HTTPException(404, "方案不存在")
    for field in ("title", "summary", "content_md", "official_url"):
        val = getattr(payload, field, None)
        if val is not None:
            setattr(plan, field, val)
    if payload.content_md is not None:
        plan.generated_by = "manual"
    db.commit()
    return {"plan": model_to_dict(plan)}


@router.delete("/admin/plans/{plan_id}")
async def delete_plan(plan_id: int, db: Session = Depends(get_db), _=Depends(require_admin)):
    plan = db.get(Plan, plan_id)
    if not plan:
        raise HTTPException(404, "方案不存在")
    db.delete(plan)
    db.commit()
    return {"ok": True}


@router.post("/admin/plans/{plan_id}/regenerate")
async def regenerate(plan_id: int, db: Session = Depends(get_db), _=Depends(require_admin)):
    old = db.get(Plan, plan_id)
    if not old:
        raise HTTPException(404, "方案不存在")
    software_key = old.software_name or str(old.software_id)
    new_plan = await get_or_create_plan(db, software_key, old.version, old.platform, force=True)
    if not new_plan:
        raise HTTPException(404, "重新生成失败：找不到软件")
    old.content_md = new_plan.content_md
    old.summary = new_plan.summary
    old.generated_by = new_plan.generated_by
    old.official_url = new_plan.official_url
    db.commit()
    return {"plan": model_to_dict(old)}


# ---------------- 反馈管理 ----------------
@router.get("/admin/feedbacks")
async def list_feedbacks(status: str = "", limit: int = 200, db: Session = Depends(get_db),
                         _=Depends(require_admin)):
    q = db.query(Feedback)
    if status:
        q = q.filter(Feedback.status == status)
    rows = q.order_by(Feedback.id.desc()).limit(limit).all()
    return {"items": [model_to_dict(f) for f in rows]}


@router.patch("/admin/feedbacks/{fb_id}")
async def update_feedback(fb_id: int, payload: FeedbackUpdateIn, db: Session = Depends(get_db),
                          _=Depends(require_admin)):
    fb = db.get(Feedback, fb_id)
    if not fb:
        raise HTTPException(404, "反馈不存在")
    if payload.status is not None:
        fb.status = payload.status
    if payload.reply is not None:
        fb.reply = payload.reply
    db.commit()
    return {"feedback": model_to_dict(fb)}


# ---------------- 统计 ----------------
@router.get("/stats/overview")
async def stats_overview(db: Session = Depends(get_db), _=Depends(require_admin)):
    total_plans = db.query(func.count(Plan.id)).scalar() or 0
    total_software = db.query(func.count(Software.id)).scalar() or 0
    total_feedback = db.query(func.count(Feedback.id)).scalar() or 0
    pending_feedback = db.query(func.count(Feedback.id)).filter(
        Feedback.status == "pending").scalar() or 0

    soft_rows = db.query(
        StatEvent.software_name, func.count(StatEvent.id)
    ).group_by(StatEvent.software_name).order_by(func.count(StatEvent.id).desc()).limit(20).all()
    ver_rows = db.query(
        StatEvent.software_name, StatEvent.version, func.count(StatEvent.id)
    ).filter(StatEvent.version != "").group_by(
        StatEvent.software_name, StatEvent.version
    ).order_by(func.count(StatEvent.id).desc()).limit(20).all()
    plat_rows = db.query(
        StatEvent.platform, func.count(StatEvent.id)
    ).group_by(StatEvent.platform).order_by(func.count(StatEvent.id).desc()).all()
    type_rows = db.query(
        StatEvent.event_type, func.count(StatEvent.id)
    ).group_by(StatEvent.event_type).all()

    top_plans = db.query(Plan).order_by(
        (Plan.valid_count + Plan.invalid_count).desc(), Plan.view_count.desc()
    ).limit(10).all()

    return {
        "total_plans": total_plans,
        "total_software": total_software,
        "total_feedback": total_feedback,
        "pending_feedback": pending_feedback,
        "by_software": [{"name": n or "(未知)", "count": c} for n, c in soft_rows],
        "by_version": [{"name": f"{n} {v}", "count": c} for n, v, c in ver_rows],
        "by_platform": [{"name": p or "(未知)", "count": c} for p, c in plat_rows],
        "by_event": [{"name": t, "count": c} for t, c in type_rows],
        "top_plans": [
            {
                "id": p.id, "name": f"{p.software_name} {p.version} · {p.platform}",
                "view": p.view_count, "install": p.install_count,
                "valid": p.valid_count, "invalid": p.invalid_count,
            }
            for p in top_plans
        ],
    }


# ---------------- 公共：反馈 & 事件 ----------------
@router.post("/feedback")
async def create_feedback(payload: FeedbackIn, db: Session = Depends(get_db)):
    fb = Feedback(
        plan_id=payload.plan_id, software_name=payload.software_name,
        version=payload.version, platform=payload.platform,
        vote=payload.vote, content=payload.content,
    )
    db.add(fb)
    db.commit()
    db.refresh(fb)
    if payload.plan_id:
        plan = db.get(Plan, payload.plan_id)
        if plan:
            if payload.vote == "valid":
                plan.valid_count = (plan.valid_count or 0) + 1
            elif payload.vote == "invalid":
                plan.invalid_count = (plan.invalid_count or 0) + 1
            db.commit()
    return {"feedback": model_to_dict(fb)}


@router.post("/events")
async def create_event(payload: EventIn):
    from ..database import SessionLocal
    db = SessionLocal()
    try:
        record_event(db, payload.software_name, payload.version, payload.platform, payload.event_type)
    finally:
        db.close()
    return {"ok": True}
