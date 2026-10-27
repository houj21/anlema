"""配置加载：~/.claude/settings.json -> 环境变量 -> .env 多级回退。"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent  # server/

# 手动加载 .env（不依赖 python-dotenv 的自动查找时机）
_ENV_FILE = BASE_DIR / ".env"
if _ENV_FILE.exists():
    for _line in _ENV_FILE.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if not _line or _line.startswith("#") or "=" not in _line:
            continue
        _k, _v = _line.split("=", 1)
        _k, _v = _k.strip(), _v.strip().strip('"').strip("'")
        if _k and _k not in os.environ:
            os.environ[_k] = _v


def _load_claude_settings() -> dict:
    """从 ~/.claude/settings.json 的 env 字段读取 AI 凭证。"""
    for candidate in (
        Path(os.path.expanduser("~")) / ".claude" / "settings.json",
        Path(os.path.expanduser("~")) / ".claude.json",
    ):
        try:
            if candidate.exists():
                data = json.loads(candidate.read_text(encoding="utf-8"))
                env = data.get("env") or {}
                if isinstance(env, dict) and env:
                    return env
        except Exception:
            continue
    return {}


_CLAUDE_ENV = _load_claude_settings()


def _pick(key: str, default: str = "") -> str:
    return os.environ.get(key) or _CLAUDE_ENV.get(key) or default


class Settings:
    # ---- AI ----
    ANTHROPIC_AUTH_TOKEN: str = _pick("ANTHROPIC_AUTH_TOKEN", "")
    ANTHROPIC_BASE_URL: str = _pick("ANTHROPIC_BASE_URL", "https://api.anthropic.com").rstrip("/")
    LLM_MODEL: str = _pick("LLM_MODEL", "") or _pick("ANTHROPIC_MODEL", "claude-sonnet-4-5")
    # 多个候选模型，逗号分隔，依次尝试
    LLM_MODEL_FALLBACKS: str = _pick(
        "LLM_MODEL_FALLBACKS", "claude-sonnet-4-5,claude-3-7-sonnet-latest,claude-3-5-sonnet-latest"
    )
    GITHUB_TOKEN: str = _pick("GITHUB_TOKEN", "")
    AI_TIMEOUT: float = float(_pick("AI_TIMEOUT", "180"))
    AI_TEMPERATURE: float = float(_pick("AI_TEMPERATURE", "0.3"))

    # ---- 服务 ----
    HOST: str = _pick("HOST", "0.0.0.0")
    PORT: int = int(_pick("PORT", "8899"))
    DB_PATH: Path = Path(_pick("DB_PATH", str(BASE_DIR / "data" / "anlema.db")))
    # 云端库（Turso / libSQL）：配了就走远程，留空则用本地 SQLite 文件
    TURSO_DATABASE_URL: str = _pick("TURSO_DATABASE_URL", "")
    TURSO_AUTH_TOKEN: str = _pick("TURSO_AUTH_TOKEN", "")
    CORS_ORIGINS: str = _pick("CORS_ORIGINS", "*")

    # ---- 限流与额度 ----
    # 单 IP 每分钟最多触发几次方案生成（0 表示不限制）
    GENERATE_RATE_LIMIT: int = int(_pick("GENERATE_RATE_LIMIT", "3"))
    # 每天最多跑几次 AI 生成，防止接口被刷爆模型额度（0 表示不限制）
    AI_DAILY_QUOTA: int = int(_pick("AI_DAILY_QUOTA", "100"))

    # ---- 管理后台 ----
    ADMIN_USERNAME: str = _pick("ADMIN_USERNAME", "admin")
    ADMIN_PASSWORD: str = _pick("ADMIN_PASSWORD", "zhuanglma")

    def model_candidates(self) -> list[str]:
        seen, out = set(), []
        for m in [self.LLM_MODEL] + [x.strip() for x in self.LLM_MODEL_FALLBACKS.split(",")]:
            if m and m not in seen:
                seen.add(m)
                out.append(m)
        return out

    @property
    def admin_token(self) -> str:
        """简单口令登录：token = sha256(username:password:salt)。"""
        raw = f"{self.ADMIN_USERNAME}:{self.ADMIN_PASSWORD}:zhuang-le-ma"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    @property
    def ai_enabled(self) -> bool:
        return bool(self.ANTHROPIC_AUTH_TOKEN)


settings = Settings()


def write_env_file(**pairs) -> None:
    """把解析到的 AI 凭证写回 server/.env（保持原有行顺序）。"""
    kv = dict(pairs)
    lines: list[str] = []
    if _ENV_FILE.exists():
        lines = _ENV_FILE.read_text(encoding="utf-8").splitlines()

    out, hit = [], set()
    for line in lines:
        stripped = line.strip()
        key = stripped.split("=", 1)[0].strip() if "=" in stripped else ""
        if key in kv:
            out.append(f"{key}={kv[key]}")
            hit.add(key)
        else:
            out.append(line)
    for k in kv:
        if k not in hit:
            out.append(f"{k}={kv[k]}")
    _ENV_FILE.write_text("\n".join(out) + "\n", encoding="utf-8")
