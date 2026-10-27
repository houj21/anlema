# -*- coding: utf-8 -*-
"""轻量限流与 AI 额度保护。

分成两层，各管一段：

1. 进程内滑动窗口：挡住单实例上的高频请求。serverless 里每个实例的内存
   互相独立，所以只能拦住"打同一实例"的情况，够应付脚本狂刷。
2. 每日全局配额：AI 生成次数存在数据库里统计，跨实例共享。这才是真正
   兜底的东西——就算被分散打到几十个实例，一天也超不过这个上限。
"""
from __future__ import annotations

import time
from collections import defaultdict, deque
from datetime import datetime

from fastapi import HTTPException, Request
from sqlalchemy import func
from sqlalchemy.orm import Session

from .models import StatEvent

_WINDOWS: dict[tuple[str, str], deque] = defaultdict(deque)


def client_ip(request: Request) -> str:
    """取真实客户端 IP：Vercel 会把原始地址放在 x-forwarded-for 最左侧。"""
    xff = (request.headers.get("x-forwarded-for") or "").strip()
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def check_rate(request: Request, *, key: str, limit: int, window: int) -> None:
    """同一 IP 在 window 秒内超过 limit 次，直接抛 429。"""
    ip = client_ip(request)
    now_ts = time.time()
    bucket = _WINDOWS[(key, ip)]
    while bucket and now_ts - bucket[0] > window:
        bucket.popleft()
    if len(bucket) >= limit:
        retry = int(window - (now_ts - bucket[0])) + 1
        raise HTTPException(
            status_code=429,
            detail=f"操作太频繁，请 {retry} 秒后再试",
            headers={"Retry-After": str(retry)},
        )
    bucket.append(now_ts)


def ai_quota_left(db: Session, *, per_day: int) -> bool:
    """当天 AI 生成次数是否还没用完（跨实例共享的全局上限）。"""
    if per_day <= 0:          # 0 或负数表示不限
        return True
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    used = (
        db.query(func.count(StatEvent.id))
        .filter(StatEvent.event_type == "generate", StatEvent.created_at >= today)
        .scalar()
        or 0
    )
    return used < per_day
