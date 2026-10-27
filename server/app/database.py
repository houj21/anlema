import logging
import sys
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from .config import settings

logger = logging.getLogger(__name__)


def _ensure_db_dir():
    """确保数据库目录可写。

    Vercel / Lambda 这类 serverless 环境的文件系统是只读的
    （只有 /tmp 可写），直接 mkdir 会抛 OSError，应用就整个起不来。
    所以先试探能不能真写进去，不行就退到 /tmp。
    """
    try:
        settings.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        probe = settings.DB_PATH.parent / ".write_probe"
        probe.touch()
        probe.unlink()
    except OSError:
        settings.DB_PATH = Path("/tmp") / settings.DB_PATH.name
        settings.DB_PATH.parent.mkdir(parents=True, exist_ok=True)


def _turso_engine_url() -> str | None:
    """云端 Turso 连接串；不满足条件时返回 None（走本地 SQLite 文件）。

    三个条件缺一不可：配了地址、配了 token、当前平台不是 Windows。
    最后一条是因为 sqlalchemy-libsql 官方只发布 Linux/macOS 的二进制，
    Windows 开发机上装不了，本地必须继续用原生 sqlite。
    """
    raw = (settings.TURSO_DATABASE_URL or "").strip()
    if not raw or not settings.TURSO_AUTH_TOKEN:
        return None
    if sys.platform.startswith("win"):
        return None
    # 用户填的可能是 libsql://host 或 https://host，这里统一取 host
    host = raw.split("://", 1)[1] if "://" in raw else raw
    return f"sqlite+libsql://{host.strip('/')}?secure=true"


_remote_url = _turso_engine_url()

if _remote_url:
    # 方言在导入这个包时才注册，所以必须显式导入（Windows 上分支不会走到）
    import sqlalchemy_libsql  # noqa: F401

    logger.info("使用云端 Turso 数据库：%s", _remote_url.split("?")[0])
    engine = create_engine(
        _remote_url,
        connect_args={"auth_token": settings.TURSO_AUTH_TOKEN},
        pool_pre_ping=True,
        future=True,
    )
else:
    _ensure_db_dir()
    engine = create_engine(
        f"sqlite:///{settings.DB_PATH.as_posix()}",
        connect_args={"check_same_thread": False},
        future=True,
    )

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
