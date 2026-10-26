# -*- coding: utf-8 -*-
"""「装了吗」服务端入口。"""
import logging
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
except Exception:
    pass

from pathlib import Path  # noqa: E402

from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402

from .config import settings, write_env_file  # noqa: E402
from .database import SessionLocal  # noqa: E402
from .routers import admin as admin_router  # noqa: E402
from .routers import plans as plans_router  # noqa: E402
from .routers import software as software_router  # noqa: E402
from .seed import seed  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("anlema")

app = FastAPI(title="装了吗 API", description="今天你装了吗？", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.CORS_ORIGINS == "*" else settings.CORS_ORIGINS.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(software_router.router)
app.include_router(plans_router.router)
app.include_router(admin_router.router)


@app.on_event("startup")
async def on_startup():
    n = seed()
    logger.info("预置软件初始化完成，新增 %d 个", n)
    # 把生效的 AI 凭证写回 .env，方便下次直接读取
    write_env_file(
        ANTHROPIC_AUTH_TOKEN=settings.ANTHROPIC_AUTH_TOKEN,
        ANTHROPIC_BASE_URL=settings.ANTHROPIC_BASE_URL,
        LLM_MODEL=settings.LLM_MODEL,
    )
    if settings.ai_enabled:
        logger.info("AI 已启用：base=%s model=%s", settings.ANTHROPIC_BASE_URL, settings.LLM_MODEL)
    else:
        logger.warning("未检测到 AI Key，方案生成将降级为本地模板")


# 若管理后台已构建，直接由服务端托管：http://127.0.0.1:8899/admin/
_ADMIN_DIST = Path(__file__).resolve().parent.parent.parent / "admin" / "dist"
if _ADMIN_DIST.exists():
    app.mount("/admin", StaticFiles(directory=str(_ADMIN_DIST), html=True), name="admin")


@app.get("/")
async def index():
    return {
        "service": "装了吗",
        "slogan": "今天你装了吗？",
        "docs": "/docs",
        "admin": "/admin/" if _ADMIN_DIST.exists() else "未构建（cd admin && npx vite build）",
    }


@app.get("/api/health")
async def health():
    db = SessionLocal()
    try:
        from .models import Plan, Software
        sw = db.query(Software).count()
        pl = db.query(Plan).count()
    finally:
        db.close()
    return {
        "ok": True,
        "service": "装了吗",
        "slogan": "今天你装了吗？",
        "ai_enabled": settings.ai_enabled,
        "base_url": settings.ANTHROPIC_BASE_URL,
        "model": settings.LLM_MODEL,
        "software_count": sw,
        "plan_count": pl,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=False)
