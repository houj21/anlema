# -*- coding: utf-8 -*-
"""Vercel Serverless 入口。

Vercel 的 Python runtime 会加载本文件，识别里面的 ASGI 应用 `app`。
项目根是 server/（requirements.txt 和 app/ 都在这一层）。
"""
import sys
from pathlib import Path

# sys.path 里不一定有项目根，补上才能 `from app.main import app`
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.main import app  # noqa: E402

__all__ = ["app"]
