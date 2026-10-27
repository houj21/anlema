# 后端运维手册

> 配合 [backend-architecture.md](./backend-architecture.md) 阅读。本文只讲"怎么操作"。

## 一、环境变量

### Vercel（项目 `anlema-api`，Production）

| 变量 | 作用 | 示例 / 默认 |
| --- | --- | --- |
| `ANTHROPIC_AUTH_TOKEN` | AI 网关密钥 | `sk-...` |
| `ANTHROPIC_BASE_URL` | 网关地址 | `https://api.hcnsec.cn/v1` |
| `LLM_MODEL` | 主模型 | `MiMo-V2.6-Flash` |
| `LLM_MODEL_FALLBACKS` | 备用模型，逗号分隔 | `claude-sonnet-4-5,...` |
| `AI_TIMEOUT` | 同步 AI 调用超时（秒） | `180` |
| `ADMIN_PASSWORD` | 管理后台登录口令 | `******` |
| **`TURSO_DATABASE_URL`** | Turso 库地址 | `libsql://anlema-xxx.turso.io` |
| **`TURSO_AUTH_TOKEN`** | Turso **数据库访问** token（JWT） | `eyJhbGci...` |
| **`CORS_ORIGINS`** | 跨域白名单，逗号分隔 | 见下文 |
| `GENERATE_RATE_LIMIT` | 单 IP 每分钟生成次数，`0` = 不限 | `3` |
| `AI_DAILY_QUOTA` | 每天 AI 生成总次数，`0` = 不限 | `100` |

当前 `CORS_ORIGINS` 取值：

```
https://anlema-admin-kgihmudk.edgeone.cool,http://127.0.0.1:5173,http://localhost:5173,http://127.0.0.1:8899,http://localhost:8899
```

### 本地 `server/.env`

本地同样需要 `TURSO_*`（迁移脚本要用），但**运行时不生效**——Windows 上 `database.py` 会主动忽略它们，继续用 `data/anlema.db`。

```bash
TURSO_DATABASE_URL=libsql://anlema-houj.aws-ap-northeast-1.turso.io
TURSO_AUTH_TOKEN=eyJhbGci...
CORS_ORIGINS=http://127.0.0.1:5173,http://localhost:5173,http://127.0.0.1:8899
```

> `server/.env` 已被 `.gitignore` 与 `.vercelignore` 双重排除，不会进仓库也不会进部署产物。

### 凭据类型容易搞混，务必区分

| 类型 | payload 特征 | 用途 | 能否连库 |
| --- | --- | --- | --- |
| 组织管理 token | `{"jti":..., "org_id":...}` | 调 `api.turso.tech` 建库、签发 token | ❌ 401 |
| 数据库访问 token | 含 `{"a":"rw","id":"<db-id>",...}` | 连 `libsql://`、调 `/v2/pipeline` | ✅ |

判断方法：调 `GET https://api.turso.tech/v1/organizations` 返回 200 的是**管理 token**。

签发数据库 token：

```bash
POST https://api.turso.tech/v1/organizations/{org}/databases/{db}/auth/tokens
Authorization: Bearer <管理 token>
Content-Type: application/json

{}          # 请求体可为空，返回 {"jwt": "..."}
```

管理 token 用完即可吊销，运行时只需要数据库 token。

## 二、本地开发

```powershell
cd server
pip install -r requirements.txt      # Windows 会自动跳过 sqlalchemy-libsql
py -3.13 -m uvicorn app.main:app --host 127.0.0.1 --port 8899
```

- 健康检查：<http://127.0.0.1:8899/api/health>
- 接口文档：<http://127.0.0.1:8899/docs>
- 数据库：`server/data/anlema.db`（SQLite 文件，与线上互不影响）

验证本地仍走文件库（而不是被 `.env` 里的 Turso 配置带跑）：

```
期望：ok=True 软件=17 方案=15
若 Turso 配置误生效，方案数会变成线上值或 0
```

## 三、部署

```powershell
cd server
vercel --prod
```

- 项目已 `link` 到 `anlema-api`，生产域名 `https://anlema-api.vercel.app`
- 构建约 15–25 秒（首次装 `sqlalchemy-libsql` 会慢一些）
- Vercel 会读 `server/vercel.json`（`maxDuration: 300`）与 `server/api/index.py`
- **不要用网页拖拽上传**：容易多套一层目录、且项目会被自动识别成 `fastapi` 框架预设，导致 `rewrites` 失效、所有路由 404

## 四、数据迁移

```powershell
cd server
py -3.13 tools/migrate_to_turso.py --dry      # 预览本地行数，不联网
py -3.13 tools/migrate_to_turso.py            # 正式迁移
py -3.13 tools/migrate_to_turso.py --proxy    # 网络异常时走本机代理
```

特性：

- **只读本地库**，不写不删；执行前建议备份 `data/anlema.db`
- **幂等**：`INSERT OR IGNORE`，重复跑不会重复插入（实测第二次 `379 变 379`）
- **自动清洗悬空外键**（本地未开外键约束，历史 `plan_id` 可能指向已删方案）

备份：

```powershell
Copy-Item data/anlema.db "data/anlema.db.bak-$(Get-Date -Format yyyyMMdd-HHmmss)"
```

## 五、验证清单

### 5.1 冒烟（只读）

```powershell
cd server
py -3.13 tests/remote_smoke.py https://anlema-api.vercel.app --proxy
```

覆盖：健康检查、`/docs`、软件搜索、版本列表、方案列表、后台登录、统计接口、CORS 头。

### 5.2 写入与持久化

```powershell
py -3.13 tests/remote_smoke.py https://anlema-api.vercel.app --proxy --write
```

写入一条反馈后，直接查 Turso 的 `feedbacks` 行数应 +1（说明真的落到远程库，而不是 `/tmp`）。

### 5.3 AI 生成

```powershell
# 触发 fast 生成，然后轮询同一个 plan
POST /api/plans/generate  {"software":"git","platform":"windows","fast":true,"force":true}
GET  /api/plans/{id}
```

期望：先返回 `generated_by=template`，约 150 秒后变 `ai`。若超过 300 秒仍为 `template`，说明 `maxDuration` 或后台任务链路退化了。

### 5.4 CORS 白名单

```powershell
curl.exe -i -H "Origin: https://example.com" https://anlema-api.vercel.app/api/health
# 期望：不出现 access-control-allow-origin

curl.exe -i -H "Origin: https://anlema-admin-kgihmudk.edgeone.cool" https://anlema-api.vercel.app/api/health
# 期望：access-control-allow-origin: https://anlema-admin-kgihmudk.edgeone.cool
```

### 5.5 限流

同一 IP 连续 4 次 `POST /api/plans/generate`，第 4 次应为 `429 操作太频繁`。

## 六、故障排查

| 现象 | 可能原因 | 处理 |
| --- | --- | --- |
| 所有路径都返回 `{"detail":"Not Found"}` | 项目被识别为 `fastapi` 框架预设，`rewrites` 失效 | 项目 Settings → Framework Preset 改为 `Other`，重新部署 |
| 冷启动后数据清零 | 没连上 Turso，退回了 `/tmp` | 检查 `TURSO_*` 是否配在 **Production** 环境；确认 `sqlalchemy-libsql` 装上了（构建日志） |
| `invalid JWT token` | 用了组织管理 token 连库 | 换成数据库访问 token（见 1.3） |
| `FOREIGN KEY constraint failed` | 本地数据有悬空外键 | 迁移脚本已内置清洗；自定义脚本需自行处理 |
| 迁移脚本 TLS 握手失败 | 系统代理被 `httpx` 自动读取 | 脚本已设 `trust_env=False`；仍失败时加 `--proxy` |
| 线上 `*.vercel.app` 请求超时 | 本机 DNS 被污染（解析到 `104.244.46.186`） | 所有线上测试加代理 `-x http://127.0.0.1:7897` |
| 后台打开报 CORS 错误 | 前端域名不在白名单 | 更新 `CORS_ORIGINS` 后重新部署 |
| AI 一直只有模板 | 日额度用尽 / 后台任务被中断 | 查当天 `generate` 事件数；确认 `maxDuration` 仍是 300 |
| 正常用户被 429 | 同 IP（如公司 NAT）多人高频使用 | 调大 `GENERATE_RATE_LIMIT` 或设为 0 |

## 七、额度与成本

| 项目 | 免费额度 | 当前用量 |
| --- | --- | --- |
| Turso 存储 | 9 GB | < 1 MB |
| Turso 读 | 5 亿行/月 | 可忽略 |
| Turso 写 | 2500 万行/月 | 可忽略 |
| Vercel 函数 | Hobby 100 GB-Hrs/月 | 单次 AI 生成约 147 秒 |
| AI token | 取决于网关套餐 | 每次生成约 3–6k tokens |

按 `AI_DAILY_QUOTA=100` 估算，最坏情况每天 100 次生成、约 30–60 万 tokens。

## 八、安全注意事项

1. **数据库 token 只存在 Vercel 环境变量与本地 `.env`**，不进代码、不进 Git、不进部署产物。
2. 组织管理 token 只在签发数据库 token 时用一次，用完建议吊销。
3. 怀疑泄漏时轮换流程：重新签发数据库 token → 更新 Vercel 环境变量 → 重新部署 → 吊销旧 token。
4. `ADMIN_PASSWORD` 是弱口令（`zhuanglma`）时，配合已收紧的 CORS 风险可控，但仍建议换成强口令并定期更换。
5. 部署产物不含 `tests/`、`tools/`、`data/`、`.env`（见 `server/.vercelignore`）。
