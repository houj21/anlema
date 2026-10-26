# -*- coding: utf-8 -*-
"""「装了吗」端到端自检脚本：跑完整业务流程（用户端 + 管理端）。

用法：
    py -3.13 tests/e2e.py [base_url]
默认 base_url = http://127.0.0.1:8899
"""
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import httpx

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8899"
PASS, FAIL = "✅", "❌"
results = []


def check(name: str, cond: bool, extra: str = "") -> bool:
    results.append((name, cond, extra))
    print(f"{PASS if cond else FAIL} {name} {extra}")
    return cond


def main() -> int:
    # AI 网关对长文本很慢（实测完整方案 200-330 秒），超时必须留够
    c = httpx.Client(base_url=BASE, timeout=420)

    # 1. 健康检查
    h = c.get("/api/health").json()
    check("健康检查", h["ok"], f"AI={'开' if h['ai_enabled'] else '关'} 软件={h['software_count']} 方案={h['plan_count']}")

    # 2. 一句话解析软件
    sw = c.post("/api/resolve", json={"query": "我想装 Redis"}).json()["software"]
    check("一句话解析软件", sw["name"].lower().startswith("redis"), f"-> {sw['name']}")

    # 3. 版本列表
    v = c.get(f"/api/softwares/{sw['slug']}/versions").json()
    check("获取版本列表", len(v["versions"]) > 0, f"latest={v['latest']} src={v['source']} 共{len(v['versions'])}个")

    # 4. 生成 Windows 方案
    p = c.post("/api/plans/generate", json={
        "software": sw["name"], "version": v["latest"], "platform": "windows"
    }).json()["plan"]
    md = p["content_md"]
    check("生成 Windows 方案", bool(md) and "一键安装脚本" in md,
          f"id={p['id']} 来源={p['generated_by']} 长度={len(md)}")
    check("方案含 PowerShell 脚本块", "```powershell" in md)
    check("方案含环境变量小节", "环境变量" in md)
    check("方案含安装验证小节", "安装验证" in md)
    check("方案含常见问题小节", "常见问题" in md)
    check("方案含执行后建议小节", "执行后建议" in md)
    check("方案无学习资源推荐", "教程" not in md and "学习路线" not in md)

    # 5. 同一个软件再生成 macOS 方案（应各自独立）
    p2 = c.post("/api/plans/generate", json={
        "software": sw["name"], "version": v["latest"], "platform": "macos"
    }).json()["plan"]
    check("生成 macOS 方案", "```bash" in p2["content_md"], f"id={p2['id']}")
    check("Win/Mac 方案互不覆盖", p["id"] != p2["id"])

    # 6. 缓存命中（不 force 时返回同一条）
    p3 = c.post("/api/plans/generate", json={
        "software": sw["name"], "version": v["latest"], "platform": "windows"
    }).json()["plan"]
    check("方案按 软件+版本+平台 缓存", p3["id"] == p["id"], f"id={p3['id']}")

    # 7. 官方安装包类软件（VS Code）
    vs = c.post("/api/resolve", json={"query": "vscode"}).json()["software"]
    pv = c.post("/api/plans/generate", json={
        "software": vs["name"], "version": "latest", "platform": "windows"
    }).json()["plan"]
    check("官方安装包类软件给出下载链接",
          ("官方安装包" in pv["content_md"]) and ("http" in pv["content_md"]),
          f"->{vs['name']}")

    # 8. 一键安装计数
    c.post(f"/api/plans/{p['id']}/install")
    check("记录一键安装次数", c.get(f"/api/plans/{p['id']}").json()["plan"]["install_count"] >= 1)

    # 9. 有效 / 无效
    c.post(f"/api/plans/{p['id']}/vote", json={"vote": "valid"})
    c.post(f"/api/plans/{p['id']}/vote", json={"vote": "invalid", "content": "winget 报 0x80070422"})
    pl = c.get(f"/api/plans/{p['id']}").json()["plan"]
    check("标记有效/无效", pl["valid_count"] >= 1 and pl["invalid_count"] >= 1,
          f"👍{pl['valid_count']} 👎{pl['invalid_count']}")

    # 10. 文字反馈
    fb = c.post("/api/feedback", json={
        "plan_id": p["id"], "software_name": sw["name"], "version": v["latest"],
        "platform": "windows", "vote": "none", "content": "脚本跑通了，谢谢！"
    }).json()["feedback"]
    check("提交文字反馈", fb["id"] > 0, f"id={fb['id']}")

    # 11. 后台登录（错口令 / 对口令）
    r401 = c.post("/api/admin/login", json={"username": "admin", "password": "wrong"})
    check("错口令被拒绝", r401.status_code == 401)
    token = c.post("/api/admin/login", json={"username": "admin", "password": "zhuanglma"}).json()["token"]
    check("正确口令登录成功", bool(token))
    adm = {"X-Admin-Token": token}
    check("后台鉴权生效", c.get("/api/admin/check", headers=adm).status_code == 200)
    check("无 token 访问后台被拒", c.get("/api/admin/feedbacks").status_code == 401)

    # 12. 后台：反馈管理
    fbs = c.get("/api/admin/feedbacks", headers=adm).json()["items"]
    check("后台查看反馈", len(fbs) >= 1, f"共{len(fbs)}条")
    c.patch(f"/api/admin/feedbacks/{fbs[0]['id']}", headers=adm,
            json={"status": "resolved", "reply": "收到，已修"})
    check("后台标记反馈已处理",
          c.get("/api/admin/feedbacks?status=resolved", headers=adm).json()["items"][0]["status"] == "resolved")

    # 13. 后台：查看 / 编辑 / 重新生成 / 删除方案
    plans = c.get("/api/plans?q=", headers=adm).json()["items"]
    check("后台查看方案列表", len(plans) >= 1, f"共{len(plans)}条")
    edited = c.patch(f"/api/admin/plans/{p['id']}", headers=adm,
                     json={"summary": "后台人工改过的摘要"}).json()["plan"]
    check("后台编辑方案摘要", edited["summary"] == "后台人工改过的摘要")
    edited2 = c.patch(f"/api/admin/plans/{p['id']}", headers=adm,
                      json={"content_md": edited["content_md"] + "\n\n> 后台补充：记得配密码\n"}).json()["plan"]
    check("后台编辑正文并标记为人工",
          edited2["generated_by"] == "manual" and "后台补充" in edited2["content_md"])
    regen = c.post(f"/api/admin/plans/{p['id']}/regenerate", headers=adm).json()["plan"]
    check("后台 AI 重新生成", len(regen["content_md"]) > 200, f"来源={regen['generated_by']}")

    # 14. 统计
    st = c.get("/api/stats/overview", headers=adm).json()
    check("统计接口", st["total_plans"] >= 1 and len(st["by_platform"]) >= 1,
          f"方案={st['total_plans']} 软件={st['total_software']} 反馈={st['total_feedback']}")
    check("统计含软件维度", any(x["name"] for x in st["by_software"]),
          " / ".join(f"{x['name']}:{x['count']}" for x in st["by_software"][:3]))

    # 15. 删除（放最后，避免影响其它用例）
    c.delete(f"/api/admin/plans/{p2['id']}", headers=adm)
    check("后台删除方案", c.get(f"/api/plans/{p2['id']}").status_code == 404)

    ok = sum(1 for _, c2, _ in results if c2)
    print(f"\n{'='*46}\n通过 {ok}/{len(results)}")
    return 0 if ok == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
