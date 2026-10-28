# 装了吗 📦

> **今天你装了吗？**
>
> 输入一句「我想装 MySQL」，选个版本和平台，AI 给你写一份带中文注释的安装方案 —— 复制脚本，或者直接点「一键安装」让它自己跑完。

一个帮学编程的同学「一键装软件」的小系统，由三部分组成：

> 想了解系统全貌？看 [平台整体设计](docs/architecture.md)（三端架构图 + 核心功能 + 详细设计）。

| 部分 | 技术栈 | 目录 |
| --- | --- | --- |
| 桌面 APP（用户端） | Electron + React + Tailwind（Shadcn 风格组件） | `desktop/` |
| 服务端 | Python FastAPI + SQLite（本地）/ Turso（线上，双引擎） | `server/` |
| Web 管理后台 | React + Tailwind | `admin/` |

---

## 文档

| 文档 | 内容 |
| --- | --- |
| [平台整体设计](docs/architecture.md) | **先看这篇**：三端架构图、核心功能、数据模型、三端详细设计、决策记录 |
| [后端架构设计](docs/backend-architecture.md) | 为什么从 `/tmp` SQLite 换成 Turso、双引擎原理、AI 超时改造、限流与 CORS |
| [后端运维手册](docs/operations.md) | 环境变量清单、数据迁移、部署流程、验证清单、故障排查 |
| [桌面端打包与分发](docs/desktop-release.md) | Windows 打包、GitHub Actions 自动发布、签名方案、打包踩坑 |
| [本地开发指南](docs/development.md) | 三端同时跑起来、后端地址三套来源、功能对比、UI 复用现状 |

---

## 快速开始

端口一览：服务端 `8899`、桌面端渲染进程 `5173`（Electron 窗口自动拉起）、管理后台 `5180`。

### 0. 环境要求

- Node.js ≥ 18
- Python ≥ 3.9（本项目用 `py -3.13` 验证；系统默认 3.8 跑不动新版 FastAPI）

### 1. 启动服务端

```powershell
cd server
pip install -r requirements.txt
py -3.13 -m uvicorn app.main:app --host 127.0.0.1 --port 8899
```

首次启动会自动建库、写入 17 个预置软件。健康检查：<http://127.0.0.1:8899/api/health>
接口文档：<http://127.0.0.1:8899/docs>

### 2. 启动桌面 APP

```powershell
cd desktop
npm install
npm run dev          # 开发模式：Vite + Electron 热更新
# 或者
npm run build
npm start            # 构建后启动（等价 npm start:built）
```

### 3. 打开管理后台

两种方式任选：

```powershell
# A. 已被服务端托管（需先执行过 admin 的 build）
#    浏览器打开 http://127.0.0.1:8899/admin/

# B. 独立开发模式
cd admin
npm install
npm run dev          # http://127.0.0.1:5180 ，已配 /api 代理到 8899
```

默认口令：**`zhuanglma`**（在 `server/.env` 里改 `ADMIN_PASSWORD`）

---

## AI 配置

服务端读取顺序（后者覆盖前者）：

1. `~/.claude/settings.json` 的 `env.ANTHROPIC_AUTH_TOKEN` / `env.ANTHROPIC_BASE_URL`
2. 进程环境变量
3. `server/.env`

`.env` 关键项：

```ini
ANTHROPIC_AUTH_TOKEN=sk-xxxx            # 必填，AI API Key
ANTHROPIC_BASE_URL=https://xxx/v1       # OpenAI Chat Completions 兼容地址
LLM_MODEL=auto                          # 主模型
LLM_MODEL_FALLBACKS=auto,claude-...     # 依次尝试的备用模型
GITHUB_TOKEN=                           # 可选，避免 GitHub API 匿名限流
```

- 接口格式为 OpenAI 兼容的 `POST {base}/v1/chat/completions`；若 `base` 已以 `/v1` 结尾则不会重复拼接。
- **没配 Key 也能跑**：方案生成会自动降级为本地内置模板（脚本/环境变量/验证/FAQ 一样齐全），
  桌面端右上角会显示「本地模板」而不是「AI 在线」。

---

## 功能一览

### 桌面端
- 一句话搜索（「我想装 MySQL」）→ AI 提炼软件名
- 版本策略：**本地缓存 → npm / PyPI / GitHub Releases / Maven Central → 预置兜底 → AI**
- 平台自动检测当前系统，可手动切 Windows / macOS / Linux
- Markdown 方案渲染 + 代码高亮 + 每个代码块独立复制按钮
- **一键安装**：把方案里的脚本落盘后真实执行，实时回传日志
  - Windows 用 PowerShell，macOS/Linux 用 Bash
  - 「管理员/Sudo 模式」：Windows `Start-Process -Verb RunAs`（UAC 弹窗）、macOS `osascript`、Linux `pkexec`
  - 支持中途停止、退出码提示
- 方案「有效 / 无效」标记 + 文字反馈

### 服务端
- 方案按 **软件 + 版本 + 平台** 唯一缓存，重复请求直接命中
- 记录浏览、一键安装、有效/无效、选择等事件，供后台统计

### 管理后台
- 口令登录
- 方案管理：搜索、编辑 Markdown（左编辑右预览）、AI 重新生成、删除
- 反馈管理：按 `待处理 / 已处理` 筛选、标记已处理、回复
- 数据统计：软件 / 版本 / 平台 / 事件分布 + 最受欢迎方案

---

## API 速查

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/health` | 健康检查（含 AI 是否启用） |
| GET | `/api/softwares?q=` | 软件列表 |
| POST | `/api/resolve` | 一句话 → 软件实体 |
| GET | `/api/softwares/{key}/versions?refresh=` | 版本列表 |
| POST | `/api/plans/generate` | 生成/读取方案 `{software, version, platform, force}` |
| GET | `/api/plans/{id}` | 方案详情 |
| POST | `/api/plans/{id}/install` | 一键安装计数 |
| POST | `/api/plans/{id}/vote` | 有效/无效 |
| POST | `/api/feedback` | 文字反馈 |
| POST | `/api/admin/login` | 口令登录 → token |
| PATCH/DELETE | `/api/admin/plans/{id}` | 编辑 / 删除方案 |
| POST | `/api/admin/plans/{id}/regenerate` | AI 重新生成 |
| GET/PATCH | `/api/admin/feedbacks` | 反馈列表 / 处理 |
| GET | `/api/stats/overview` | 统计总览 |

后台接口需要请求头 `X-Admin-Token`。

---

## 测试

```powershell
# 1) 服务端全流程自检（30 项：解析 / 版本 / 生成 / 缓存 / 投票 / 反馈 / 后台 / 统计）
cd server
py -3.13 tests/e2e.py
```

前端冒烟（Playwright，需先 `npm run build` 两端 + 服务端已启动）：

```powershell
cd tools/uitest
npm install
node serve.mjs        # 另开窗口：托管 desktop/dist(5190) 与 admin/dist(5191)
node run.mjs          # 浏览器视角：桌面端 8 项 + 管理后台 7 项
node electron.mjs     # 真实 Electron 窗口：一键安装执行链路 7 项
```

> 若本机 chromium 版本与 playwright 不匹配，用 `CHROME_PATH=<chrome.exe> node run.mjs` 指定。

## 打包发布

```powershell
cd desktop
npm run dist:win      # 产出 release/ZhuangLeMa-Setup-<version>.exe（NSIS，可选安装目录）
npm run dist:dir      # 只产出 release/win-unpacked/ 绿色版，不压安装包
```

配置写在 `desktop/package.json` 的 `build` 字段：appId、productName、图标（`build/icon.ico`）、
NSIS（中文界面、允许改安装目录、创建桌面/开始菜单快捷方式）。

推一个 `v*` tag 会自动在 GitHub Actions 上构建 Windows 包并发布到 Release，
完整流程见 [docs/desktop-release.md](docs/desktop-release.md)。

> 国内网络提示：electron-builder 需要从 GitHub 下载 nsis / winCodeSign 等二进制，
> 直连常 `ETIMEDOUT`。加镜像即可：
> `$env:ELECTRON_BUILDER_BINARIES_MIRROR="https://registry.npmmirror.com/-/binary/electron-builder-binaries/"`

---

## 目录结构

```
anlema/
├── server/                  # FastAPI 服务端
│   ├── app/
│   │   ├── main.py          # 入口、CORS、静态托管 /admin
│   │   ├── config.py        # 配置（.env / ~/.claude/settings.json 多级回退）
│   │   ├── models.py        # 软件 / 版本 / 方案 / 反馈 / 事件
│   │   ├── catalog.py       # 17 个预置软件 + 安装提示
│   │   ├── version_sources.py  # npm / PyPI / GitHub / Maven
│   │   ├── ai.py            # OpenAI 兼容客户端（多模型回退）
│   │   ├── planner.py       # Prompt + 本地模板兜底
│   │   ├── service.py       # 业务编排
│   │   └── routers/         # software / plans / admin
│   ├── tests/e2e.py
│   └── .env
├── desktop/                 # Electron + React
│   ├── electron/main.cjs    # 窗口 + 脚本执行（提权 / 日志回传）
│   ├── electron/preload.cjs
│   └── src/                 # React UI
├── admin/                   # 管理后台（React）
├── tools/uitest/            # Playwright 前端冒烟
├── docs/                    # 架构 / 运维 / 打包 / 开发指南
├── .github/workflows/       # 打 tag 自动构建 Windows 包并发布 Release
└── PROGRESS.md              # 开发进度与踩坑记录
```

---

## 已知限制 / 踩坑记录

- 系统默认 `python` 若是 3.8，请显式用 `py -3.13`。
- GitHub Releases 匿名接口限流（60 次/小时）：配 `GITHUB_TOKEN` 或依赖预置版本兜底。
- PowerShell 5.1 会把无 BOM 的 UTF-8 脚本当 ANSI 读，中文注释会乱码 —— 桌面端落盘脚本时
  已自动加 BOM 并在开头强制 UTF-8 输出。
- 「一键安装」会真实执行安装命令，请确认方案内容可信；提权模式会弹 UAC / 输入密码。
- 打包相关（productName 必须英文、CI 里别注入 `GH_TOKEN`、静默安装要带 `/D`）
  见 [docs/desktop-release.md](docs/desktop-release.md)。
- 后端 CORS 已收紧为白名单：新增前端域名要同步改 `CORS_ORIGINS` 再重新部署。
- 方案生成有两层限流（3 次/分钟/IP + 100 次/天全局），用 `GENERATE_RATE_LIMIT`、
  `AI_DAILY_QUOTA` 调整，见 [docs/operations.md](docs/operations.md)。
- 桌面端与管理后台的 UI 组件是各自复制的（Button / Card / Badge），**改样式要改两处**。
- 管理后台登录页把默认口令提示写在了页面上，线上部署前建议隐藏。
