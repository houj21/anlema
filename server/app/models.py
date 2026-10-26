from __future__ import annotations

import datetime as dt

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint

from .database import Base


def now() -> dt.datetime:
    return dt.datetime.now()


class Software(Base):
    __tablename__ = "softwares"

    id = Column(Integer, primary_key=True)
    name = Column(String(128), nullable=False)
    slug = Column(String(128), nullable=False, unique=True, index=True)
    aliases = Column(Text, default="")           # 逗号分隔别名
    category = Column(String(64), default="other")
    official_url = Column(String(512), default="")
    docs_url = Column(String(512), default="")
    icon = Column(String(16), default="📦")
    tagline = Column(String(256), default="")    # 一句话吐槽向说明
    # 版本来源：npm / pypi / github / maven / go / rust / manual
    source_kind = Column(String(32), default="manual")
    source_key = Column(String(256), default="")  # npm 包名 / pypi 包名 / github owner/repo / maven group:artifact
    # 安装形态：script（脚本安装） / link（官方安装包，给链接）
    install_type = Column(String(16), default="script")
    homepage = Column(String(512), default="")
    created_at = Column(DateTime, default=now)
    updated_at = Column(DateTime, default=now, onupdate=now)


class Version(Base):
    __tablename__ = "versions"
    __table_args__ = (UniqueConstraint("software_id", "version", name="uq_software_version"),)

    id = Column(Integer, primary_key=True)
    software_id = Column(Integer, ForeignKey("softwares.id", ondelete="CASCADE"), index=True)
    version = Column(String(64), nullable=False)
    is_latest = Column(Integer, default=0)
    released_at = Column(String(64), default="")
    source = Column(String(32), default="cache")  # cache / npm / pypi / github / maven / ai
    created_at = Column(DateTime, default=now)


class Plan(Base):
    """安装方案：软件 + 版本 + 平台 唯一。"""
    __tablename__ = "plans"
    __table_args__ = (
        UniqueConstraint("software_id", "version", "platform", name="uq_plan_key"),
    )

    id = Column(Integer, primary_key=True)
    software_id = Column(Integer, ForeignKey("softwares.id", ondelete="CASCADE"), index=True)
    software_name = Column(String(128), default="")   # 冗余，便于后台检索
    version = Column(String(64), nullable=False)
    platform = Column(String(32), nullable=False)     # windows / macos / linux
    title = Column(String(256), default="")
    summary = Column(String(512), default="")
    content_md = Column(Text, default="")
    official_url = Column(String(512), default="")    # 官方下载/安装页
    generated_by = Column(String(32), default="ai")   # ai / template / manual
    status = Column(String(16), default="active")     # active / archived
    view_count = Column(Integer, default=0)
    install_count = Column(Integer, default=0)
    valid_count = Column(Integer, default=0)
    invalid_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=now)
    updated_at = Column(DateTime, default=now, onupdate=now)


class Feedback(Base):
    __tablename__ = "feedbacks"

    id = Column(Integer, primary_key=True)
    plan_id = Column(Integer, ForeignKey("plans.id", ondelete="SET NULL"), nullable=True)
    software_name = Column(String(128), default="")
    version = Column(String(64), default="")
    platform = Column(String(32), default="")
    vote = Column(String(16), default="none")   # valid / invalid / none
    content = Column(Text, default="")
    status = Column(String(16), default="pending")  # pending / resolved
    reply = Column(Text, default="")
    created_at = Column(DateTime, default=now)


class StatEvent(Base):
    """选择次数统计事件。"""
    __tablename__ = "stat_events"

    id = Column(Integer, primary_key=True)
    software_name = Column(String(128), default="", index=True)
    version = Column(String(64), default="")
    platform = Column(String(32), default="")
    event_type = Column(String(32), default="select", index=True)  # select/generate/install/vote
    created_at = Column(DateTime, default=now)
