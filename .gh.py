# -*- coding: utf-8 -*-
"""临时脚本：查看 GitHub Actions 运行状态与 Release 资产。"""
import sys

import httpx

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

C = httpx.Client(timeout=30, proxy="http://127.0.0.1:7897", trust_env=False)
API = "https://api.github.com/repos/houj21/anlema"

r = C.get(f"{API}/actions/runs?per_page=3")
print("=== 工作流运行 ===")
if r.status_code == 200:
    for w in r.json().get("workflow_runs", []):
        print(f"  {w['name']:<20} | {w['head_branch']:<8} | {w['status']:<12} | {w['conclusion']}")
else:
    print("  ", r.status_code, r.text[:160])

r2 = C.get(f"{API}/releases/latest")
print("\n=== 最新 Release ===")
if r2.status_code == 200:
    d = r2.json()
    print("  tag:", d.get("tag_name"))
    assets = d.get("assets") or []
    if not assets:
        print("  （暂无资产）")
    for a in assets:
        print(f"  - {a['name']:<38} {a['size'] / 1024 / 1024:.1f} MB")
else:
    print("  ", r2.status_code, r2.text[:160])
