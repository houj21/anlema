# 装了吗 · 开发进度

> 口号：**今天你装了吗？**
> 状态：**✅ 全部完成，端到端验证通过**（2026-10-25）

## 验收结果

| 验证项 | 命令 | 结果 |
| --- | --- | --- |
| 服务端 API 全流程 | `py -3.13 server/tests/e2e.py` | ✅ 30/30 |
| 桌面端 + 管理后台 UI 流程 | `node tools/uitest/run.mjs` | ✅ 20/20 |
| 真实 Electron 窗口内「一键安装」链路 | `node tools/uitest/electron.mjs` | ✅ 11/11（含 `Stop` 自动降级、版本不一致提示、版本不存在直接拦截） |
| 桌面端 / 管理后台生产构建 | `npx vite build` | ✅ 均通过 |
| Windows 安装包（electron-builder） | `npm run dist:win` | ✅ `release/装了吗-Setup-1.0.0.exe` 87.4 MB，静默安装 + 启动实测通过 |

> 冒烟脚本已纳入仓库 `tools/uitest/`，可随时复跑（三条命令见 README「测试」一节）。

## 三个模块

### 1. 服务端 `server/`
- FastAPI + SQLAlchemy + SQLite（`server/data/anlema.db`）
- 表：`softwares` / `versions` / `plans`（软件+版本+平台唯一）/ `feedbacks` / `stat_events`
- 预置 17 个软件，启动时自动建库 + 同步目录元信息
- 版本策略：缓存 → npm / PyPI / GitHub Releases / Maven Central → 预置兜底 → AI
- AI：OpenAI 兼容客户端，多模型依次回退；失败自动降级本地模板
- 已托管管理后台静态资源：`/admin/`
- 自检脚本：`py -3.13 tests/e2e.py`

### 2. 桌面端 `desktop/`
- Electron 主进程：窗口、脚本落盘与执行、日志流式回传、提权、停止
- 渲染层：React + Tailwind（Shadcn 风格手写组件）+ Markdown 高亮 + 复制按钮
- 一键安装提权：Win `Start-Process -Verb RunAs`（日志 tail）、macOS `osascript`、Linux `pkexec`
- **PS 脚本落盘加 UTF-8 BOM** + 脚本头强制 UTF-8 输出（否则中文日志乱码）
- 日志解码优先 UTF-8，异常回退 GBK

### 3. 管理后台 `admin/`
- 口令登录（默认 `zhuanglma`，`server/.env` 可改）
- 方案：搜索 / 编辑（左编辑右预览）/ AI 重新生成 / 删除
- 反馈：状态筛选 / 标记已处理 / 回复
- 统计：概览卡片 + 软件/版本/平台/事件分布 + Top 方案

## 恢复运行（下次开机）

```powershell
# 1) 服务端
cd d:/ai/anlema/server
py -3.13 -m uvicorn app.main:app --host 127.0.0.1 --port 8899

# 2) 桌面端（二选一）
cd d:/ai/anlema/desktop
npm run dev            # 开发模式
# 或
npm run build; node_modules\electron\dist\electron.exe .

# 3) 管理后台
#    直接开 http://127.0.0.1:8899/admin/ （dist 已构建）
#    或 cd admin && npx vite  → http://127.0.0.1:5180
```

## 遗留 / 可选增强

- 安装包未做代码签名证书（双击安装时 Windows 会提示「未知发布者」，自用的话忽略即可）
- 只打了 Windows x64 包；macOS（`--mac dmg`）/ Linux（`--linux AppImage`）命令相同，但需要对应系统的构建机
- 预置软件 17 个可继续扩充（往 `server/app/catalog.py` 里加即可，会随启动自动入库）
- AI 网关出方案较慢（200-330 秒/次），方案有缓存，第二次打开同一组合是秒开；后续可做「生成中进度条 + 后台预生成热门软件」

## 问题与解决（踩坑记录）

| 问题 | 解决方案 |
| --- | --- |
| 系统默认 python 是 3.8，跑不动新版 FastAPI | 用 `py -3.13`（`D:\Users\lanba\anaconda3\python.exe`） |
| `~/.claude/settings.json` 不存在，取不到 ANTHROPIC_AUTH_TOKEN | 配置加载器多级回退：`~/.claude/settings.json` → 环境变量 → `.env`；实测回落到本机 OpenAI 兼容网关并写入 `server/.env` |
| AI 网关 base_url 已含 `/v1`，代码又拼一次 → 404 | `ai.py` 判断结尾再拼接 |
| GitHub Releases 返回空 / 匿名限流 | releases 为空回落 tags；支持可选 `GITHUB_TOKEN`；仍失败用预置版本 |
| 版本里混进 `3.16.0a1`、`weekly.2012-03-27`、`mysql-cluster-xx` | 严格 `^\d+(\.\d+){0,3}$` 过滤 + MySQL 加 `version_match` 正则 |
| Tailwind 无 `h-13` | config 补 `spacing.13` |
| `Start-Process npx electron` 起不来（%1 is not a valid Win32 application） | 直接调 `node_modules\electron\dist\electron.exe` |
| **一键安装日志中文乱码 + 脚本被当成命令回显** | PowerShell 5.1 按 ANSI 读无 BOM 的 UTF-8 脚本；改为写 UTF-8 BOM，并在脚本头设置 `$OutputEncoding` / `[Console]::OutputEncoding` 为 UTF-8 |
| 前端 favicon 404 干扰冒烟用例 | 两个 `index.html` 内联 data-URI SVG 图标 |
| **点「一键安装」像没反应** | ① 日志面板渲染在页面最底部（方案很长时在视口外）→ 改为 `fixed bottom-0` 贴底浮层；② 提权路径把 `-Verb RunAs` 和 `-RedirectStandardOutput` 混用（参数冲突）→ 改为 runner 脚本 + `StreamWriter(UTF8, AutoFlush)` 实时落盘再 tail；③ 提权启动器自身的 stderr 之前没接管道（UAC 点「否」看不到原因）→ 补上 |
| **一键安装执行了错的代码块** | `extractScript` 原来取「第一个」脚本块，MySQL 方案里前面是「官方安装包」的 winget/choco 短命令。改为：优先「一键安装脚本」小节 → 其次平台匹配最长块 → 再退任意脚本块最长；UI 上加「N 行脚本」徽标，肉眼可核对（MySQL 8.0.36 = 87 行） |
| **一键安装跑完报 `No package found matching input criteria`，还显示退出码 0** | ① 我们自己目录里 4 个 winget ID 是编的（已 `winget show` 实测修正）：`Oracle.MySQL.Server→Oracle.MySQL`、`Apache.Maven→(winget 无此包，改用 choco)`、`Memurai.Memurai-Developer→Redis.Redis`、`Nginx.Nginx→nginxinc.nginx`，另补 `nvm→CoreyButler.NVMforWindows`；② Prompt 加了硬规则：失败即停（`$LASTEXITCODE` 非 0 就 exit）、禁止编造包 ID（必须用给出的已验证 ID）、版本不存在不许硬写 `--version` 要自动回退并说明；③ 本地兜底模板同样加了退出码检查；④ 执行器兜底：退出码 0 但日志里出现 `No package found / 无法将…识别为 / command not found` 等，判定为「很可能没装成功」并给出建议。新生成的 MySQL 方案已实测：正确 ID ×3、错误 ID ×0、`$LASTEXITCODE` ×4 |
| **一键安装「只打了 2 行日志就说装好了」，实际啥也没装** | 根因是把 `$ErrorActionPreference = 'Stop'` 放在了脚本头：winget/choco 是**原生命令**，失败时 PowerShell 包装成 NativeCommandError，`Stop` 下脚本直接终止，**退出码仍是 0** → 日志断在「包管理器就绪」，UI 却显示成功。修：脚本头改 `'Continue'`，每条安装命令后显式判断 `$LASTEXITCODE` 并 `exit $LASTEXITCODE`；已安装检测从 `Get-Command` 改成 `winget list --id X --exact` |
| **`mysql` 命令在终端里找不到** | 安装后 bin 目录没进 PATH（模板原来只输出注释示例）。修：catalog 每个软件加 `bin_paths`（MySQL 8.4/8.0/5.7、Node、Go、PostgreSQL 16/17），模板改为**真实探测并写入用户级 PATH**，验证前刷新 `$env:Path` 再 `Get-Command`，失败时明确提示「重开终端」并以 2 退出 |
| **模板升级后用户仍看到旧脚本** | 方案是缓存文本（`generated_by=template`），模板改了也不会重新生成。修：`TEMPLATE_VERSION` + 隐藏标记 `<!-- zlm-template N -->`，`get_or_create_plan` 命中缓存时校验标记，过期自动重新生成；桌面端渲染前剔除 HTML 注释 |
| **「Successfully installed」之后 MySQL 还是不能用** | winget 装 `Oracle.MySQL` 只落**程序文件**（`C:\Program Files\MySQL\MySQL Server 8.4`），不建数据目录、不注册服务 → `MySQL84` 服务不存在、`C:\ProgramData\MySQL\MySQL Server 8.4` 也没有。修：软件知识库补上 MySQL 的真实坑（winget 只有 8.4.x、装完要 `mysqld --initialize` + 注册服务），并由 `after` 字段强制写进方案的「执行后建议」 |
| **选了 8.0.40 却装了 8.4.9，界面还说成功** | 包管理器里只有 8.4.9，AI 不会主动说明。修：① 前端把 `plan.version` 作为 `expectedVersion` 传给主进程；② 执行器从输出里解析实际版本（winget `Version 8.4.9` / 程序 `Ver 8.0.44`），不一致就追加「你要的是 X，实际装的是 Y」；③ 检测到 `Found an existing package already installed` 时说明「这次是升级」；④ Prompt 要求 winget 前打印版本可能不同 |
| **点「生成方案」几分钟没反应、像卡死** | 根因：AI 客户端改成流式后，**httpx 的 read timeout 只作用于单次 read 调用，整体耗时不限**，实测单模型拖到 298 秒才超时，再回退下一个模型又等 5 分钟；界面还没有任何进度反馈。修：① 自己掐表，给整个生成（含回退）设总预算，超支立刻降级模板；② **fast 模式**：首次生成先秒回本地模板（实测 **0.3 秒**），AI 在后台慢慢写（预算 600 秒，人工编辑过的方案不覆盖），写完自动 `upgrade`；③ 前端显示「已等待 N 秒」+「AI 正在后台补充，写完自动替换」徽标；④ 主模型换成 `MiMo-V2.6-Flash`（`step-5-preview` 实测只吐 reasoning_content、白等 127 秒，已挪到回退链末尾） |
| **Nginx 装完自检报 `CreateFile() "C:\WINDOWS\system32\conf/nginx.conf" failed`** | nginx 是绿色版，按**当前目录**找 `conf/`、`logs/`；而脚本在 `C:\WINDOWS\system32` 下跑；且 winget 给的 `WinGet\Links\nginx.exe` 只是**符号链接**，`cd` 到 Links 也不行。修：① `_verify_block` 先用 `(Get-Item (Get-Command X).Source).Target` 还原真实路径，`Push-Location` 到安装目录再执行 `verify` 命令链；② 自检不过就 `exit 1`（原来是打印一句"检查失败"然后退出码 0，假成功）；③ 执行器 `FAIL_PATTERNS` 补 `[emerg]`、`test failed`、`配置语法检查失败`，退出码 0 但日志报错也判失败；④ Prompt 规则 13 要求 AI 同样处理 |
| **「已经是最新版」被当成安装失败** | 已装同版本时 winget 返回 `-1978335189`（0x8A150015 无可用升级），脚本判 `$LASTEXITCODE -ne 0` 就报"安装失败"。修：模板单独识别这个码，打印"本机已经是这个版本，跳过安装"并继续验证 |
| **版本下拉里有「包管理器根本装不了」的版本**（如 Nginx 1.24.0） | 版本列表来自我写死的 `catalog.fallback_versions`（nginx 写了 1.27.3/1.26.2/1.24.0），而 winget 只保留每个包**当前仍在提供**的版本，1.24.0 早被删掉 → 选得到、装不了。修：① 新增 `app/pkg_versions.py`，Windows 下版本列表**直接查 `winget show --versions`**（带 6 小时缓存），`source=winget`；② `/api/softwares/{key}/versions` 增加 `platform` 参数，前端把当前平台传过去；③ 徽标显示「版本来源：winget 仓库（本机能直接装）」；④ `catalog` 里 nginx 的兜底版本改成 winget 实测值。Nginx 现在 24 个版本（1.31.8→1.27.2），不含 1.24.0 |
| **选 8.0.40，却每次都装成 8.4.9** | `winget show Oracle.MySQL --versions` 实测**根本没有 8.0.40**（可用 8.4.9/8.4.8/8.0.43/8.0.42/8.0.41/8.0.39/8.0.36），而脚本的 `winget install` 没带 `--version` → 默认装最新 8.4.9。修（按用户要求「没有我要的版本就别装」）：① 模板脚本加**版本预检**，`$Avail -notcontains $WantVersion` 就打印可用版本并 `exit 3`；② `winget install` 带 `--version <所选版本>`；③ **执行器兜底**：点「确认执行」后主进程先 `winget show --id X --versions` 本地校验，对不上直接拦下、脚本一行都不跑（冒烟实测 `code=3` 且 `SHOULD-NOT-RUN` 未出现）；④ Prompt 规则 12 改为硬规则：禁止"提示一句就装最新版"；⑤ 版本下拉改为 winget 真实可装版本，并清掉 DB 里编造的 `8.0.40/9.1.0` 与混进来的 `mysql-cluster-*` |
| **AI 生成经常降级成本地模板** | 网关 `auto` 被路由到推理模型，只返回 `reasoning_content`、`content=null`。改为：模型定死 `step-5-preview`，回退链 `MiMo-V2.6-Flash → DeepSeek-V4.1-Flash → Qwen3.8-27B`；AI 客户端改为**流式 SSE**接收（避免长文本读超时，中断时若已收到完整结构则采用部分结果）；方案 `max_tokens` 8000→4500。实测成功生成 6275 字方案（MiMo-V2.6-Flash，331 秒） |
