from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class ResolveIn(BaseModel):
    query: str


class VersionsOut(BaseModel):
    software: dict
    latest: Optional[str] = None
    versions: list[dict] = []
    source: str = "cache"


class GenerateIn(BaseModel):
    software: str
    version: Optional[str] = None
    platform: Optional[str] = None
    force: bool = False
    # fast=true：先秒回本地模板，AI 在后台写好后再自动升级
    fast: bool = False


class PlanOut(BaseModel):
    id: int
    software_id: int
    software_name: str
    version: str
    platform: str
    title: str
    summary: str
    content_md: str
    official_url: str = ""
    generated_by: str
    view_count: int = 0
    install_count: int = 0
    valid_count: int = 0
    invalid_count: int = 0
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class PlanUpdateIn(BaseModel):
    title: Optional[str] = None
    summary: Optional[str] = None
    content_md: Optional[str] = None
    official_url: Optional[str] = None


class FeedbackIn(BaseModel):
    plan_id: Optional[int] = None
    software_name: str = ""
    version: str = ""
    platform: str = ""
    vote: str = "none"      # valid / invalid / none
    content: str = ""


class FeedbackUpdateIn(BaseModel):
    status: Optional[str] = None
    reply: Optional[str] = None


class EventIn(BaseModel):
    software_name: str = ""
    version: str = ""
    platform: str = ""
    event_type: str = "select"


class LoginIn(BaseModel):
    username: str = ""
    password: str = ""


def model_to_dict(obj) -> dict:
    d = {}
    for c in obj.__table__.columns:
        v = getattr(obj, c.name)
        if hasattr(v, "isoformat"):
            v = v.isoformat()
        d[c.name] = v
    return d
