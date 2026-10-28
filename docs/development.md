# 本地开发指南

面向要在本机同时跑起三端做开发/联调的场景。记录的是**实际验证过的行为**，不是配置文件的字面意思。

## 一、三端总览

| 端 | 目录 | 端口 | 启动命令 | 职责 |
| --- | --- | --- | --- | --- |
| 服务端 | `server/` | **8899** | `py -3.13 -m uvicorn app.main:app --host 127.0.0.1 --port 8899` | 数据 + AI 生成 + 统计 |
| 桌面端 | `desktop/` | 渲染 **5173** + Electron 窗口 | `npm run dev` | 用户端：搜软件、拿方案、真装 |
| 管理后台 | `admin/` | **5180** | `npm run dev` | 运营端：看数据、改方案、处理反馈 |

管理后台的 5180 由 `admin/vite.config.ts` 指定，且已配 `/api` 代理到 8899。

## 二、一次跑起来

三个终端各开一个（后端必须先起，前端才能拿到数据）：

```powershell
# 终端 1：后端
cd server
py -3.13 -m uvicorn app.main:app --host 127.0.0.1 --port 8899

# 终端 2：桌面端（Vite + Electron 一起起）
cd desktop
npm run dev

# 终端 3：管理后台
cd admin
npm run dev
```

确认都活着：

```powershell
Get-NetTCPConnection -LocalPort 8899,5173,5180 -State Listen
```

管理后台默认口令 `zhuanglma`（改 `server/.env` 的 `ADMIN_PASSWORD`）。

## 三、后端地址三套来源（最容易踩坑的地方）

同一个前端代码，跑在不同环境会连到不同后端：

| 场景 | 地址来源 | 实际连哪里 | 是否跨域 |
| --- | --- | --- | --- |
| 桌面端开发 | `desktop/.env.development` | `http://127.0.0.1:8899` | 是，走 CORS |
| 桌面端打包版 | `desktop/.env.production` | `https://anlema-api.vercel.app` | 是，走 CORS |
| 管理后台 | Vite 代理 `/api` | `http://127.0.0.1:8899` | 否（同源） |

代码入口是 `desktop/src/lib/api.ts` 的 `getApiBase()`，优先级：

```
localStorage['zlm:api-base']  >  import.meta.env.VITE_API_BASE  >  兜底 127.0.0.1:8899
```

**用户在设置里手动填过的地址优先级最高**，会覆盖打包版默认值。

两个推论：

1. 调 `CORS_ORIGINS` 时，管理后台不受影响（同源代理），桌面端会立刻受影响。
2. 桌面端发的是跨域请求，后端日志里能看到 `OPTIONS` 预检，这是正常的，不是异常。

## 四、三端功能对比

| 维度 | 桌面端（用户端） | 管理后台 |
| --- | --- | --- |
| 定位 | 搜软件 → 拿方案 → **真装** | 看数据 → 改方案 → 处理反馈 |
| 视图组织 | 单页条件渲染，无路由 | 3 个 Tab（方案 / 反馈 / 统计）+ 登录门 |
| 调用接口数 | 9 个，全部公开 | 9 个，其中 7 个走 `/api/admin/` |
| 鉴权 | 无 | `X-Admin-Token` 头，401 自动登出 |
| 本机能力 | 有（提权执行、UAC、杀进程） | 无（浏览器沙箱） |
| 数据方向 | **生产**（生成 / 投票 / 埋点） | **消费** |

两者是互补而非重叠关系。共通接口只有 `/api/health` 一个。

`/api/plans` 形似而实异：桌面端走 `/api/plans/generate` 和 `/api/plans/{id}` 读写单个，
后台走 `/api/plans?limit=200` 拉全量。

### 桌面端独有的 Electron 能力

`desktop/electron/preload.cjs` 通过 `window.zlm` 暴露 5 个 IPC：

| IPC | 用途 |
| --- | --- |
| `app:info` | 自动识别当前平台（App.tsx:89） |
| `script:run` | 执行安装脚本 |
| `script:stop` | 中止执行（`taskkill`） |
| `app:openExternal` | 打开外部链接 |
| `onOutput` / `onDone` | 实时日志回传 |

主进程 `main.cjs` 里几个关键实现：

- `writeScript`（:167）：写临时脚本到 `os.tmpdir`，ps1 会加 UTF-8 BOM 并强制 UTF-8 输出
- 提权：Windows `Start-Process -Verb RunAs`（:229）、macOS `osascript`（:264）、Linux `pkexec`（:274）
- `preflightVersionCheck`（:138）：用 `winget show` 预检版本是否存在，不存在直接拦下
- `FAIL_PATTERNS`（:81）：退出码 0 但输出含错误关键字，也判定为失败

### 管理后台独有功能

口令登录 + token 持久化；方案增删改 + AI 重新生成；反馈标记已处理 / 回复；
统计看板（`BarList` 软件 / 版本 / 平台 / 事件分布 + top plans）；`?api=` URL 参数指定后端。

## 五、验证三端数据同源

两端读的是同一个库，可以用这个办法确认（都是 15 就对了）：

```powershell
# 桌面端视角
Invoke-RestMethod http://127.0.0.1:8899/api/health
# -> plan_count = 15

# 管理后台视角
$pw = @{password="zhuanglma"} | ConvertTo-Json
$tok = Invoke-RestMethod http://127.0.0.1:8899/api/admin/login -Method POST -Body $pw -ContentType "application/json"
(Invoke-RestMethod "http://127.0.0.1:8899/api/plans?limit=200" -Headers @{"X-Admin-Token"=$tok.token}).items.Count
# -> 15
```

管理后台看板上的四个数字（软件 / 方案 / 反馈 / 待处理）应与上面两个结果一致；
对不上说明两端读的不是同一个库。

## 六、接口归属速查

| 归属 | 端点 |
| --- | --- |
| 桌面端常用 | `/api/health` `/api/softwares` `/api/resolve` `/api/softwares/{key}/versions` `/api/plans/generate` `/api/plans/{id}` `/api/plans/{id}/install` `/api/plans/{id}/vote` `/api/events` |
| 管理后台常用 | `/api/admin/login` `/api/plans` `/api/admin/plans/{id}` `/api/admin/plans/{id}/regenerate` `/api/admin/feedbacks` `/api/admin/feedbacks/{id}` `/api/stats/overview` |

> `POST /api/plans/generate` 返回的是 `{"plan": {...}}` **包装结构**，
> 方案本体在 `plan` 子对象里（`plan.id` / `plan.generated_by` / `plan.content_md`）。

## 七、UI 组件复用现状：0%

两端 `components/` 下的 `Button` / `Card` / `Badge` 是**各自复制**后分化，不是共享包：

- desktop 拆成 `components/ui/{button,badge,card}.tsx`；admin 合并为单个 `components/ui.tsx`
- 尺寸已漂移：Button `h-11 px-5`（desktop）vs `h-10 px-4`（admin）
- Card 实现不同：desktop 是 `forwardRef` + `CardHeader/CardTitle/CardContent`；admin 是普通函数
- Badge 两处代码逐字符相同，纯复制

**改样式要同时改两处**，或者另建共享包。

## 八、已知瑕疵与注意事项

| 问题 | 位置 | 影响 |
| --- | --- | --- |
| 后台登录页把默认口令写在页面上 | `admin/src/App.tsx` 登录框下方 | 本地无所谓，线上部署会泄露口令提示 |
| `app:pickSave` 注册但未暴露 | `electron/main.cjs:406` | 死代码 |
| `runScript` 传了 `expectedVersion` 但类型未声明 | `App.tsx:241` vs `:48` | 类型不一致 |
| 只配了 Windows 打包 | workflow 单平台 | macOS 需另配构建机 + 证书 |

其他：

- 系统默认 `python` 若是 3.8，必须显式用 `py -3.13`。
- 打包时 electron-builder 要下载 nsis / winCodeSign，直连常超时，配镜像：
  `$env:ELECTRON_BUILDER_BINARIES_MIRROR="https://registry.npmmirror.com/-/binary/electron-builder-binaries/"`
- 后端在 Windows 走本地 SQLite，在 Vercel 走 Turso，开发体验一致但底层不同，
  详见 [backend-architecture.md](backend-architecture.md)。

## 九、日常命令速查

```powershell
# 重新起后端（先杀端口再起）
Get-NetTCPConnection -LocalPort 8899 -State Listen |
  ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }

# 跑服务端自检（30 项）
cd server; py -3.13 tests/e2e.py

# 两端构建（前端冒烟测试前需要先构建）
cd desktop; npm run build
cd ../admin; npm run build

# 前端冒烟（Playwright）
cd tools/uitest; node serve.mjs; node run.mjs; node electron.mjs

# 打 Windows 包
cd desktop; npm run dist:win
```

打包与分发的完整流程见 [desktop-release.md](desktop-release.md)。
