# -*- coding: utf-8 -*-
"""线上后端冒烟测试（只读，不写数据库）。

专门用来验证把 server 部署到 Vercel / 任意公网地址后是否真的活着。
只读接口为主：serverless 环境（Vercel）文件系统通常不可写，
SQLite 建库、写方案、投票这类接口失败不一定是代码问题。

用法：
    py -3.13 tests/remote_smoke.py https://your-app.vercel.app
    py -3.13 tests/remote_smoke.py https://your-app.vercel.app --write   # 额外测写接口
"""
import sys
import time

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
except Exception:
    pass

import httpx

PASS, FAIL, WARN = "✅", "❌", "⚠️ "
results: list[bool] = []

# 冷启动可能很慢（Vercel 首次请求 10-30 秒很常见），超时给足
TIMEOUT = 60.0


def check(name: str, cond: bool, extra: str = "") -> bool:
    print(f"{PASS if cond else FAIL} {name} {extra}")
    results.append(cond)
    return cond


def call(c: httpx.Client, method: str, path: str, **kw):
    """返回 (是否成功, 说明)。把状态码和报错原文打出来，方便定位。"""
    t0 = time.time()
    try:
        r = c.request(method, path, **kw)
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"
    ms = int((time.time() - t0) * 1000)
    if r.status_code >= 400:
        return False, f"HTTP {r.status_code} ({ms}ms) {r.text[:160]}"
    return True, f"{ms}ms"


def main() -> int:
    if len(sys.argv) < 2:
        print("用法：py -3.13 tests/remote_smoke.py https://your-app.vercel.app")
        return 2
    base = sys.argv[1].rstrip("/")
    want_write = "--write" in sys.argv

    print(f"\n🔍 测试目标：{base}\n")
    # 默认不读 http_proxy：本机代理会把请求劫走，测出来的 502 是假象。
    # 确实需要代理时加 --proxy。
    c = httpx.Client(base_url=base, timeout=TIMEOUT, follow_redirects=True,
                     trust_env="--proxy" in sys.argv)

    # 1. 健康检查（最重要：它还会查一次数据库，能验证 DB 是否可用）
    ok, info = call(c, "GET", "/api/health")
    if ok:
        h = c.get("/api/health").json()
        check("健康检查", bool(h.get("ok")),
              f"AI={'开' if h.get('ai_enabled') else '关'} 模型={h.get('model')} "
              f"软件={h.get('software_count')} 方案={h.get('plan_count')}")
        if h.get("software_count", 0) == 0:
            print(f"   {WARN} 软件数为 0：线上数据库是空的或没初始化（Vercel 上 SQLite 常如此）")
    else:
        check("健康检查", False, info)
        print(f"   {WARN} 后端根本没起来。先去 Vercel 后台看 Functions 日志。")
        return 1

    # 2. 接口文档（FastAPI 自带，能打开说明路由注册正常）
    ok, info = call(c, "GET", "/docs")
    check("接口文档 /docs", ok, info)

    # 3. 软件列表
    ok, info = call(c, "GET", "/api/softwares", params={"q": "mysql"})
    n = 0
    if ok:
        n = len(c.get("/api/softwares", params={"q": "mysql"}).json().get("items", []))
    check("软件搜索", ok and n > 0, f"{info} 命中 {n} 个")

    # 4. 版本列表（会去查 npm/PyPI/GitHub，验证出网）
    ok, info = call(c, "GET", "/api/softwares/mysql/versions")
    check("版本列表", ok, info)

    # 5. 方案列表
    ok, info = call(c, "GET", "/api/plans", params={"q": "", "limit": 5})
    check("方案列表", ok, info)

    # 6. 管理端登录（只验证接口通，token 不落盘）
    ok, info = call(c, "POST", "/api/admin/login",
                    json={"username": "admin", "password": "zhuanglma"})
    token = ""
    if ok:
        token = c.post("/api/admin/login",
                       json={"username": "admin", "password": "zhuanglma"}).json().get("token", "")
    check("后台登录", ok and bool(token), info)

    # 7. 带 token 取统计（验证 X-Admin-Token 鉴权链）
    if token:
        ok, info = call(c, "GET", "/api/stats/overview", headers={"X-Admin-Token": token})
        check("统计接口（带 token）", ok, info)
    else:
        check("统计接口（带 token）", False, "没拿到 token，跳过")

    # 8. 跨域头（后台页面在别的域名上，必须允许）
    ok, _ = call(c, "OPTIONS", "/api/health",
                 headers={"Origin": "https://anlema-admin-kgihmudk.edgeone.cool",
                          "Access-Control-Request-Method": "GET"})
    r = c.options("/api/health",
                  headers={"Origin": "https://anlema-admin-kgihmudk.edgeone.cool",
                           "Access-Control-Request-Method": "GET"})
    allow = r.headers.get("access-control-allow-origin", "")
    check("跨域 CORS", allow in ("*", "https://anlema-admin-kgihmudk.edgeone.cool"),
          f"Access-Control-Allow-Origin={allow or '(无)'}")

    # 9. 写接口（默认不跑：Vercel 上文件系统只读，失败不代表代码有问题）
    if want_write:
        ok, info = call(c, "POST", "/api/feedback",
                        json={"plan_id": 1, "content": "线上冒烟测试", "contact": ""})
        check("写接口：提交反馈", ok, info)
        if not ok:
            print(f"   {WARN} 写失败在 Vercel 上是预期的：SQLite 无法写入。需要换 Postgres/Turso。")

    passed = sum(results)
    total = len(results)
    print(f"\n{'🎉' if passed == total else '⚠️ '} 通过 {passed}/{total}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
