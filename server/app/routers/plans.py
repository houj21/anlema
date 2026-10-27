# -*- coding: utf-8 -*-
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..models import Feedback, Plan, StatEvent
from ..ratelimit import ai_quota_left, check_rate
from ..schemas import GenerateIn, PlanUpdateIn, model_to_dict
from ..service import get_or_create_plan, normalize_platform, record_event

router = APIRouter(prefix="/api", tags=["plans"])


@router.post("/plans/generate")
async def generate(payload: GenerateIn, request: Request, background_tasks: BackgroundTasks,
                   db: Session = Depends(get_db)):
    # 第一层：单 IP 频率限制，挡住脚本连续调用
    check_rate(request, key="generate", limit=settings.GENERATE_RATE_LIMIT, window=60)
    platform = normalize_platform(payload.platform) or "windows"
    # 第二层：当天 AI 总额度用完就只返回模板，不再触发后台生成
    if background_tasks is not None and not ai_quota_left(db, per_day=settings.AI_DAILY_QUOTA):
        background_tasks = None
    plan = await get_or_create_plan(
        db, payload.software, payload.version, platform, payload.force, payload.fast,
        background_tasks=background_tasks,
    )
    if not plan:
        raise HTTPException(404, "没找到这个软件")
    record_event(db, plan.software_name, plan.version, platform, "generate")
    return {"plan": model_to_dict(plan)}


@router.get("/plans/{plan_id}")
async def get_plan(plan_id: int, db: Session = Depends(get_db)):
    plan = db.get(Plan, plan_id)
    if not plan:
        raise HTTPException(404, "方案不存在")
    plan.view_count = (plan.view_count or 0) + 1
    db.commit()
    return {"plan": model_to_dict(plan)}


@router.post("/plans/{plan_id}/install")
async def mark_install(plan_id: int, db: Session = Depends(get_db)):
    plan = db.get(Plan, plan_id)
    if not plan:
        raise HTTPException(404, "方案不存在")
    plan.install_count = (plan.install_count or 0) + 1
    db.commit()
    record_event(db, plan.software_name, plan.version, plan.platform, "install")
    return {"ok": True}


@router.post("/plans/{plan_id}/vote")
async def vote(plan_id: int, payload: dict, db: Session = Depends(get_db)):
    """用户标记方案有效 / 无效。"""
    plan = db.get(Plan, plan_id)
    if not plan:
        raise HTTPException(404, "方案不存在")
    vote_value = (payload or {}).get("vote", "none")
    if vote_value == "valid":
        plan.valid_count = (plan.valid_count or 0) + 1
    elif vote_value == "invalid":
        plan.invalid_count = (plan.invalid_count or 0) + 1
    content = (payload or {}).get("content", "")
    db.add(Feedback(
        plan_id=plan.id, software_name=plan.software_name, version=plan.version,
        platform=plan.platform, vote=vote_value, content=content,
    ))
    db.commit()
    record_event(db, plan.software_name, plan.version, plan.platform, vote_value)
    return {"ok": True}


@router.get("/plans")
async def list_plans(q: str = "", platform: str = "", limit: int = 100,
                     db: Session = Depends(get_db)):
    query = db.query(Plan)
    if q:
        like = f"%{q.lower()}%"
        query = query.filter(Plan.software_name.ilike(like) | Plan.version.ilike(like))
    if platform:
        query = query.filter(Plan.platform == platform)
    rows = query.order_by(Plan.updated_at.desc()).limit(limit).all()
    return {"items": [model_to_dict(p) for p in rows]}
