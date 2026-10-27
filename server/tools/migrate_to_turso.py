# -*- coding: utf-8 -*-
"""把本地 SQLite 数据迁移到 Turso（libSQL）。

为什么不用 SQLAlchemy 直连：官方 sqlalchemy-libsql 只发布 Linux/macOS 二进制，
Windows 开发机装不上。所以这里走 Turso 的 HTTP API（/v2/pipeline），只依赖 httpx，
跨平台可用，且不需要在本地安装任何 libSQL 客户端。

用法（在 server 目录下）：
    py -3.13 tools/migrate_to_turso.py              # 执行迁移
    py -3.13 tools/migrate_to_turso.py --dry        # 只预览不写入
    py -3.13 tools/migrate_to_turso.py --proxy      # 网络不通时走本机代理

凭据读取顺序：环境变量 -> server/.env 中的 TURSO_DATABASE_URL / TURSO_AUTH_TOKEN
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sqlite3
import sys
from pathlib import Path
from urllib.parse import urlsplit

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

import httpx  # noqa: E402
from dotenv import load_dotenv  # noqa: E402

from sqlalchemy.schema import CreateIndex, CreateTable  # noqa: E402

from app import models  # noqa: F401,E402  导入以注册所有表
from app.database import Base, engine as local_engine  # noqa: E402

# 外键依赖顺序：父表在前
TABLE_ORDER = ["softwares", "versions", "plans", "feedbacks", "stat_events"]
BATCH = 80

# 本地 SQLite 默认不校验外键，历史数据里可能有悬空引用；
# Turso 会严格校验，所以迁移时把这些指向不存在父记录的列置 NULL。
FK_MAP: dict[str, list[tuple[str, str]]] = {
    "versions": [("software_id", "softwares")],
    "plans": [("software_id", "softwares")],
    "feedbacks": [("plan_id", "plans")],
}


def load_config() -> tuple[str, str]:
    load_dotenv(BASE_DIR / ".env")
    raw = (os.getenv("TURSO_DATABASE_URL") or "").strip()
    token = (os.getenv("TURSO_AUTH_TOKEN") or "").strip()
    if not raw or not token:
        sys.exit("缺少 TURSO_DATABASE_URL 或 TURSO_AUTH_TOKEN（检查 server/.env）")
    parts = urlsplit(raw if "://" in raw else f"https://{raw}")
    host = parts.netloc or parts.path.strip("/")
    return host, token


def to_arg(v):
    """SQLite 值 -> Turso pipeline 参数。"""
    if v is None:
        return {"type": "null"}
    if isinstance(v, bool):
        return {"type": "integer", "value": "1" if v else "0"}
    if isinstance(v, int):
        return {"type": "integer", "value": str(v)}
    if isinstance(v, float):
        return {"type": "real", "value": v}
    if isinstance(v, (dt.datetime, dt.date)):
        return {"type": "text", "value": v.isoformat(sep=" ")}
    return {"type": "text", "value": str(v)}


class Turso:
    def __init__(self, host: str, token: str, proxy: str | None):
        self.url = f"https://{host}/v2/pipeline"
        self.headers = {"Authorization": f"Bearer {token}"}
        # trust_env=False：本机系统代理会让 httpx 走 HTTP CONNECT，TLS 握手会失败。
        # 需要代理时用 --proxy 显式指定，其余情况一律直连。
        self.client = httpx.Client(timeout=90, proxy=proxy, trust_env=False)

    def run(self, statements: list[tuple[str, list | None]]) -> list:
        """一次 pipeline 执行多条语句，返回 results。"""
        reqs = []
        for sql, args in statements:
            stmt: dict = {"sql": sql}
            if args:
                stmt["args"] = args
            reqs.append({"type": "execute", "stmt": stmt})
        reqs.append({"type": "close"})
        r = self.client.post(self.url, headers=self.headers, json={"requests": reqs})
        if r.status_code != 200:
            raise RuntimeError(f"HTTP {r.status_code}: {r.text[:300]}")
        data = r.json()
        results = data.get("results") or []
        for item in results:
            if item.get("type") == "error":
                raise RuntimeError(f"SQL 执行失败: {json.dumps(item, ensure_ascii=False)[:400]}")
        return results

    def scalar(self, sql: str):
        res = self.run([(sql, None)])
        try:
            row = res[0]["response"]["result"]["rows"]
            return row[0][0]["value"] if row else None
        except (KeyError, IndexError, TypeError):
            return None


def ddl_statements() -> list[str]:
    """用 SQLAlchemy 模型生成建表/建索引语句（sqlite 方言，Turso 兼容）。"""
    out = []
    for table in Base.metadata.sorted_tables:
        sql = str(CreateTable(table).compile(local_engine)).strip()
        sql = sql.replace("CREATE TABLE ", "CREATE TABLE IF NOT EXISTS ", 1)
        out.append(sql)
    for table in Base.metadata.sorted_tables:
        for index in table.indexes:
            sql = str(CreateIndex(index).compile(local_engine)).strip()
            sql = sql.replace("CREATE INDEX ", "CREATE INDEX IF NOT EXISTS ", 1)
            sql = sql.replace("CREATE UNIQUE INDEX ", "CREATE UNIQUE INDEX IF NOT EXISTS ", 1)
            out.append(sql)
    return out


def read_local(db_path: Path) -> dict[str, tuple[list[str], list[tuple]]]:
    if not db_path.exists():
        sys.exit(f"本地数据库不存在：{db_path}")
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    data: dict[str, tuple[list[str], list[tuple]]] = {}
    try:
        for table in TABLE_ORDER:
            exists = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
            ).fetchone()
            if not exists:
                data[table] = ([], [])
                continue
            cur = conn.execute(f"SELECT * FROM {table}")
            cols = [d[0] for d in cur.description]
            rows = [tuple(r) for r in cur.fetchall()]
            data[table] = (cols, rows)
    finally:
        conn.close()
    return data


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true", help="只预览，不写入")
    ap.add_argument("--proxy", action="store_true", help="走本机 http://127.0.0.1:7897")
    ap.add_argument("--db", default=str(BASE_DIR / "data" / "anlema.db"))
    args = ap.parse_args()

    host, token = load_config()
    proxy = "http://127.0.0.1:7897" if args.proxy else None
    print(f"目标库：{host}")
    print(f"本地库：{args.db}")

    data = read_local(Path(args.db))
    total = sum(len(rows) for _, rows in data.values())
    print("\n本地数据：")
    for table in TABLE_ORDER:
        print(f"  {table:<12} {len(data[table][1])} 行")
    print(f"  合计         {total} 行")

    if args.dry:
        print("\n--dry 模式，未写入任何数据")
        return 0

    api = Turso(host, token, proxy)

    ddl = ddl_statements()
    print(f"\n建表/建索引：{len(ddl)} 条语句")
    for i in range(0, len(ddl), BATCH):
        api.run([(s, None) for s in ddl[i:i + BATCH]])
    print("  ✅ 表结构就绪")

    # 本地各表的主键集合，用于识别悬空外键
    valid_ids = {
        t: {r[cols.index("id")] for r in rows}
        for t, (cols, rows) in data.items()
        if rows and "id" in cols
    }
    fixed_total = 0

    for table in TABLE_ORDER:
        cols, rows = data[table]
        if not rows:
            print(f"\n{table}: 无数据，跳过")
            continue
        before = api.scalar(f"SELECT COUNT(*) FROM {table}")
        placeholders = ",".join("?" for _ in cols)
        col_sql = ",".join(f'"{c}"' for c in cols)
        # INSERT OR IGNORE：目标库已有的同 id 记录保留，重跑不会产生重复
        sql = f'INSERT OR IGNORE INTO {table} ({col_sql}) VALUES ({placeholders})'
        written = 0
        for i in range(0, len(rows), BATCH):
            chunk = rows[i:i + BATCH]
            args_rows = []
            for row in chunk:
                row = list(row)
                for col, ref in FK_MAP.get(table, []):
                    if col in cols:
                        idx = cols.index(col)
                        if row[idx] is not None and row[idx] not in valid_ids.get(ref, set()):
                            row[idx] = None   # 悬空引用置空，避免 Turso 外键校验失败
                            fixed_total += 1
                args_rows.append([to_arg(v) for v in row])
            api.run([(sql, a) for a in args_rows])
            written += len(chunk)
            print(f"  {table}: {written}/{len(rows)}", end="\r", flush=True)
        after = api.scalar(f"SELECT COUNT(*) FROM {table}")
        print(f"\n{table}: 本地 {len(rows)} 行 -> 线上 {before} 变 {after}  ✅")

    if fixed_total:
        print(f"\n（清洗了 {fixed_total} 个悬空外键，已置为 NULL）")

    print("\n最终线上行数：")
    for table in TABLE_ORDER:
        print(f"  {table:<12} {api.scalar(f'SELECT COUNT(*) FROM {table}')}")
    print("\n🎉 迁移完成")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
