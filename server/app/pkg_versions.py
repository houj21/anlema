# -*- coding: utf-8 -*-
"""包管理器「真实可装」的版本查询（目前实现 winget）。

为什么需要它：我之前把版本列表写死在 catalog 里（nginx 写了 1.27.3/1.26.2/1.24.0），
但 winget 仓库只保留每个包还在提供的版本，1.24.0 早就被删了 →
 用户选 1.24.0 → 脚本里 `winget install --version 1.24.0` → 仓库没有 → 白跑一趟。
所以 Windows 上的版本下拉必须以 winget 返回为准，写死的列表只当兜底。
"""
from __future__ import annotations

import asyncio
import logging
import re
import shutil
import subprocess
import time

logger = logging.getLogger("anlema.pkg")

_CACHE: dict[str, tuple[float, list[str]]] = {}
_TTL = 6 * 3600  # 包仓库版本变动不快，缓存 6 小时
_VER_RE = re.compile(r"^\d+(\.\d+)+$")


def winget_available() -> bool:
    return shutil.which("winget") is not None


def _run_winget_versions(pkg_id: str, timeout: int = 45) -> list[str]:
    exe = shutil.which("winget")
    if not exe:
        return []
    try:
        r = subprocess.run(  # noqa: S603
            [
                exe, "show", "--id", pkg_id, "--exact", "--versions",
                "--accept-source-agreements", "--disable-interactivity",
            ],
            capture_output=True,
            timeout=timeout,
        )
    except Exception as e:  # noqa: BLE001
        logger.info("winget 查 %s 版本失败：%s", pkg_id, e)
        return []
    out = (r.stdout or b"").decode("utf-8", "replace")
    out += (r.stderr or b"").decode("utf-8", "replace")
    versions: list[str] = []
    for line in out.splitlines():
        s = line.strip().strip("│|║╔╗╚╝─━").strip()
        # winget 的表格会带框线，清洗后只剩版本号的才是真数据
        if _VER_RE.match(s) and s not in versions:
            versions.append(s)
    return versions


async def winget_versions(pkg_id: str, refresh: bool = False) -> list[str]:
    """返回 winget 里该包可装的版本（新→旧），查不到返回空列表。"""
    if not pkg_id or not winget_available():
        return []
    now = time.time()
    hit = _CACHE.get(pkg_id)
    if hit and not refresh and now - hit[0] < _TTL:
        return list(hit[1])
    vs = await asyncio.to_thread(_run_winget_versions, pkg_id)
    if vs:
        _CACHE[pkg_id] = (now, vs)
    elif hit:
        # 查询失败时别把旧数据丢了
        return list(hit[1])
    return vs
