# -*- coding: utf-8 -*-
"""安装方案生成：优先 AI，失败时降级为本地内置模板（保证端到端可用）。"""
from __future__ import annotations

import logging
import re

from .ai import AIError, chat_completion, extract_json
from .catalog import find_preset

logger = logging.getLogger("anlema.planner")

# 本地模板每改一次就 +1：老方案（不带当前标记）会在下次访问时自动重新生成，
# 否则用户会一直看到模板升级前写死的旧脚本（比如已经失效的包管理器 ID）。
TEMPLATE_VERSION = 5
TEMPLATE_MARK = f"<!-- zlm-template {TEMPLATE_VERSION} -->"


def is_stale_template(content_md: str, generated_by: str) -> bool:
    """模板生成、但模板版本已过期的方案 → 需要重新生成。"""
    if (generated_by or "") != "template":
        return False
    return TEMPLATE_MARK not in (content_md or "")

PLATFORM_CN = {"windows": "Windows", "macos": "macOS", "linux": "Linux"}
SHELL_HINT = {
    "windows": "PowerShell（Windows）",
    "macos": "Bash（macOS / zsh）",
    "linux": "Bash（Linux）",
}
CODE_LANG = {"windows": "powershell", "macos": "bash", "linux": "bash"}

SYSTEM_PROMPT = """你是「装了吗」的安装方案生成器，一个帮编程新手一键装软件的工具。

你的输出风格：轻松搞笑、口语化、像一个耐心的学长在旁边指导，但**只讲安装本身**。

严格规则：
1. 只输出 Markdown 正文，不要输出任何前言、说明、```markdown 外包裹。
2. **禁止**写软件介绍、背景知识、学习资源、教程链接、"祝你学习愉快"之类的废话。
3. **禁止**推荐课程、文档站、社区、视频教程。
4. 脚本必须是可直接运行的完整脚本，每一行关键步骤都要有中文注释。
5. 脚本里必须包含：环境检查 → 安装 → 环境变量配置 → 安装验证命令。
6. 命令必须真实存在、参数正确，禁止编造不存在的命令或 URL。
7. 涉及权限提升的地方要写明（sudo / 以管理员身份运行）。
8. 如果软件有官方安装包下载页（VS Code、IntelliJ IDEA、Docker Desktop 这类），
   必须用「## 🔗 官方安装包」小节给出官方下载链接 + 包管理器命令，不要写从零编译的脚本。
9. 版本号和平台必须严格按用户给的来，不要擅自改。**但包管理器里没有这个版本时例外**（见第 11 条）。
10. 【Windows 脚本必须失败即停】
   - 开头写 `$ErrorActionPreference = 'Stop'`
   - 每条安装命令（winget / choco / msiexec / 解压）后面立刻判断退出码，
     例如：
     ```powershell
     winget install --id X --exact --accept-source-agreements --accept-package-agreements
     if ($LASTEXITCODE -ne 0) {
         Write-Host "❌ 安装失败（退出码 $LASTEXITCODE）。建议：改用 choco install X -y，或用上面的官方安装包" -ForegroundColor Red
         exit $LASTEXITCODE
     }
     ```
   - **禁止**在脚本末尾无条件 `exit 0`；只有全部步骤成功才以 0 结束。
   - 不允许"安装失败了还继续往下写环境变量、跑验证命令"。
   - 例外：winget 返回 `-1978335189`（0x8A150015）表示"已经是这个版本、没有可升级的"，
     这不是失败，要打印"已经是这个版本，跳过安装"并继续验证。
11. 【禁止编造包名】winget 的 `--id` 必须是真实存在的包 ID：
   - 用户消息里给了「已验证的包管理器信息」时，**必须原样使用那个 ID**，不要自己改写或加后缀；
   - 没给就只写你有把握的真实 ID，否则改用 choco 或官方安装包。
12. 【没有你要的版本，就不许装】这是硬规则，优先级高于"把脚本写完"：
   - 装之前必须先查版本，把这段放在 winget install 之前：
     ```powershell
     $WantVersion = '8.0.40'
     $Avail = @(winget show --id Oracle.MySQL --exact --versions 2>&1 |
         Select-String -Pattern '^\\s*\\d+(\\.\\d+)+\\s*$' | ForEach-Object { $_.ToString().Trim() })
     if ($Avail.Count -gt 0 -and ($Avail -notcontains $WantVersion)) {
         Write-Host "❌ 包管理器里没有 $Software $WantVersion，已停止安装" -ForegroundColor Red
         Write-Host "   可用版本：$($Avail -join '、')" -ForegroundColor Yellow
         Write-Host "   不会自动改成别的版本，请回「装了吗」重新选" -ForegroundColor Yellow
         exit 3
     }
     ```
   - 然后 `winget install --id X --exact --version <用户选的版本>`。
   - **绝对禁止**：用户要 8.0.x，你装 8.4.x 或"最新版"；也禁止只提示一句就继续装。
   - 用户选的是 latest 时才允许不带 `--version`。
13. 【绿色版软件（nginx / php / redis / caddy）必须在它自己目录里跑】
   winget 装完在 `%LOCALAPPDATA%\\Microsoft\\WinGet\\Links\\nginx.exe` 给的是**符号链接**，
   真实文件在 `...\\WinGet\\Packages\\nginxinc.nginx_*\\nginx-<版本>\\`，`conf/` 和 `logs/` 就在那儿。
   - 跑 `nginx -t` 之前必须先解析真实路径并进入目录：
     ```powershell
     $Real = (Get-Item -LiteralPath (Get-Command nginx).Source).Target
     Push-Location (Split-Path $Real -Parent)
     nginx -t
     $Check = $LASTEXITCODE
     Pop-Location
     if ($Check -ne 0) { exit 1 }
     ```
   - 绝不可以在 `C:\\WINDOWS\\system32` 这种目录下直接写 `nginx -t`——
     它会把 `conf/nginx.conf` 拼成相对路径然后报 `CreateFile() failed`。
   - **自检失败必须 `exit 1`**，不能只打印一句"配置语法检查失败"然后退出码 0（那是假成功）。
14. macOS/Linux 脚本同理：`set -euo pipefail`，安装命令失败要打印可读原因并 `exit 1`，不要静默继续。
15. 【禁止 `$ErrorActionPreference = 'Stop'`】winget/choco 是原生命令，在 'Stop' 下失败会
   直接终止脚本且退出码仍是 0，用户会看到"装好了"但其实什么都没装。
   统一写 `$ErrorActionPreference = 'Continue'`，靠 `$LASTEXITCODE` 显式判断成败。

输出必须严格包含以下小节（顺序不变，标题一字不差）：

## 🎯 一句话
（一句话说明这个方案要干啥，可以皮一下，不超过 40 字）

## 🔗 官方安装包
（有官方安装包的软件才写这一节：给出官网下载链接 + winget/brew/apt 命令；纯命令行软件可写"无官方安装包，直接用下面的脚本"，不要删掉这一节）

## 📦 一键安装脚本
（一个代码块，语言标注按平台：Windows 用 ```powershell，macOS/Linux 用 ```bash。
脚本要求：
- 开头有中文说明注释
- 先检查是否已安装/是否已有权限
- 安装命令
- 环境变量写入
- 结尾自动执行验证命令并打印结果
- 关键步骤用 Write-Host / echo 输出中文进度提示）

## ▶️ 怎么运行
（2-4 步，说明复制脚本后怎么跑，Windows 要说明用 PowerShell 管理员身份的方式）

## ⚙️ 环境变量
（表格或列表：变量名 / 值 / 说明，至少给出配置命令）

## ✅ 安装验证
（代码块：给出验证命令与预期输出）

## 🩺 常见问题
（3-5 条，格式：问题 → 解决办法，都是真实会踩的坑）

## 🚀 执行后建议
（3-5 条，全是跟"装好之后要做什么"有关的动作，不写学习资源）
"""

RESOLVE_SYSTEM = """你是软件名称提炼助手。用户会用一句话描述想装的软件（可能含中英文、口语、错别字）。
你要输出严格 JSON（不要代码块、不要解释），字段：
{
  "name": "规范英文/通用名，如 MySQL",
  "slug": "小写英文短名，如 mysql",
  "category": "runtime|database|tool|editor|build|server|other",
  "source_kind": "npm|pypi|github|maven|manual",
  "source_key": "npm包名 / pypi包名 / github的owner/repo / maven的group:artifact，不确定就空字符串",
  "install_type": "script|link（有官方安装包的填 link）",
  "official_url": "官方下载或主页 URL，不确定就空字符串",
  "tagline": "一句搞笑的中文吐槽，不超过 20 字"
}
只输出 JSON。"""

VERSIONS_SYSTEM = """你是软件版本列表助手。请输出严格 JSON（不要代码块、不要解释）：
{"versions": ["版本号从新到旧最多 15 个"], "latest": "最新稳定版号"}
只输出真实存在的版本号。"""


def _platform_line(platform: str) -> str:
    return f"目标平台：{PLATFORM_CN.get(platform, platform)}（脚本语言：{SHELL_HINT.get(platform, 'Bash')}）"


async def ai_generate_plan(software: dict, version: str, platform: str,
                           timeout: int | None = None) -> str:
    """调用 AI 生成 Markdown 安装方案。timeout 是总预算（秒），后台任务可以给大一点。"""
    preset = find_preset(software.get("name", "")) or {}
    install = preset.get("install", {}) or {}
    hints = []
    for k in ("winget", "choco", "brew", "apt", "yum", "verify"):
        if install.get(k):
            hints.append(f"{k}={install[k]}")
    extra = ""
    if hints:
        extra += f"\n已知包管理器信息：{', '.join(hints)}"
    if platform == "windows":
        wid = install.get("winget")
        if wid:
            extra += (
                f"\n已验证的 winget 包 ID：{wid}"
                f"（必须原样使用这个 ID，不要改写、不要加 .Server 之类的后缀）"
            )
        else:
            extra += (
                "\n注意：该软件在 winget 仓库里没有可用包，"
                "Windows 脚本不要写 winget install，请用 choco 或官方安装包下载。"
            )
    if preset.get("official_url"):
        extra += f"\n官方站点：{preset['official_url']}"
    if preset.get("install_type") == "link":
        extra += "\n注意：该软件有官方安装包，请用「🔗 官方安装包」小节给出下载链接。"
    notes = install.get("notes") or []
    if notes:
        # 这些是「装完仍然不能用」的坑，必须写进脚本输出和常见问题，别让用户以为装好就完事
        extra += "\n必须原样体现到「常见问题」里的要点：\n- " + "\n- ".join(notes[:4])
    after = install.get("after") or []
    if after:
        extra += "\n「🚀 执行后建议」必须包含：\n- " + "\n- ".join(after[:3])
    if platform == "windows" and install.get("winget"):
        extra += (
            "\n脚本里在 winget install 之前先打印一行提示："
            "「下面装的是包管理器里可用的版本，可能和你选的版本不同」，"
            "并在结尾打印「实际装上的版本以 winget 输出为准」。"
        )

    user = (
        f"软件：{software.get('name')}\n"
        f"版本：{version}\n"
        f"{_platform_line(platform)}\n"
        f"安装形态：{software.get('install_type', 'script')}{extra}\n\n"
        f"请生成完整的 Markdown 安装方案。"
    )
    return await chat_completion(
        [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user}],
        max_tokens=4500,
        timeout=timeout,
    )


async def ai_resolve(query: str) -> dict | None:
    """一句话 → 软件信息。"""
    try:
        raw = await chat_completion(
            [{"role": "system", "content": RESOLVE_SYSTEM},
             {"role": "user", "content": f"用户说：{query}"}],
            max_tokens=500,
            temperature=0.1,
            timeout=30,
        )
        data = extract_json(raw)
        if isinstance(data, dict) and data.get("name"):
            return data
    except Exception as e:  # noqa: BLE001
        logger.warning("AI 提炼软件名失败：%s", e)
    return None


async def ai_versions(name: str) -> list[str]:
    """AI 兜底版本列表。"""
    try:
        raw = await chat_completion(
            [{"role": "system", "content": VERSIONS_SYSTEM},
             {"role": "user", "content": f"软件：{name}\n请给出真实存在的版本号列表。"}],
            max_tokens=600,
            temperature=0.1,
            timeout=40,
        )
        data = extract_json(raw)
        vs = data.get("versions") if isinstance(data, dict) else None
        if isinstance(vs, list):
            return [str(v) for v in vs if v][:15]
    except Exception as e:  # noqa: BLE001
        logger.warning("AI 版本列表失败：%s", e)
    return []


# ----------------------------------------------------------------------------
# 本地模板：AI 不可用时的兜底，同样包含完整脚本/环境变量/验证/FAQ
# ----------------------------------------------------------------------------
def _ps_header(sw: str, version: str) -> str:
    # 注意：不能设 'Stop'。winget / choco 是原生命令，失败时 PowerShell 会把它包装成
    # NativeCommandError，在 'Stop' 下脚本会直接终止，而且退出码还是 0 —— 用户看到的就是
    # 「只打了两行日志，然后说装好了」。这里用 'Continue'，失败由 $LASTEXITCODE 显式判断。
    return f"""# ============================================================
# {sw} {version} · Windows 一键安装脚本（装了吗 · 今天你装了吗？）
# 用法：右键 PowerShell → 以管理员身份运行 → 粘贴执行
# 脚本做了：检查环境 → 安装 → 写环境变量 → 验证
# ============================================================
$ErrorActionPreference = 'Continue'
$Software = '{sw}'
$Version  = '{version}'

Write-Host "🚀 开始安装 $Software $Version ..." -ForegroundColor Cyan

# ---------- 1. 检查包管理器 ----------
if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {{
    Write-Host "⚠️  没找到 winget，请先安装『应用安装程序』(App Installer)：" -ForegroundColor Yellow
    Write-Host "    https://www.microsoft.com/p/app-installer/9nblggh4nns1" -ForegroundColor Yellow
    Write-Host "    老系统也可以用 Chocolatey：https://chocolatey.org/install" -ForegroundColor Yellow
    exit 1
}}
Write-Host "✅ 包管理器就绪" -ForegroundColor Green

# ---------- 2. 检查是否已安装 ----------
"""


def _bash_header(sw: str, version: str, platform: str) -> str:
    mac = platform == "macos"
    return f"""#!/usr/bin/env bash
# ============================================================
# {sw} {version} · {'macOS' if mac else 'Linux'} 一键安装脚本（装了吗 · 今天你装了吗？）
# 用法：chmod +x install.sh && ./install.sh
# 脚本做了：检查环境 → 安装 → 写环境变量 → 验证
# ============================================================
set -euo pipefail
SOFTWARE='{sw}'
VERSION='{version}'

echo "🚀 开始安装 $SOFTWARE $VERSION ..."

# ---------- 1. 检查包管理器 ----------
"""


def _is_pinned(version: str) -> bool:
    """能不能当具体版本用（latest / stable / 空 都不算）。"""
    v = (version or "").strip().lower()
    if not v or v in ("latest", "stable", "lts", "current"):
        return False
    return bool(re.match(r"^\d+(\.\d+)*", v))


def _version_gate(software: str, version: str, install: dict) -> str:
    """Windows 版本预检：包管理器里没有这个版本就退出，绝不偷偷装最新版。"""
    wid = install.get("winget") or ""
    if not wid or not _is_pinned(version):
        return ""
    return f"""# ---------- 版本预检：没有你要的版本就不装 ----------
$WantVersion = '{version}'
$Avail = @(winget show --id {wid} --exact --versions 2>&1 |
    Select-String -Pattern '^\\s*\\d+(\\.\\d+)+\\s*$' |
    ForEach-Object {{ $_.ToString().Trim() }})
if ($Avail.Count -gt 0 -and ($Avail -notcontains $WantVersion)) {{
    Write-Host "❌ 包管理器里没有 {software} $WantVersion，已停止安装" -ForegroundColor Red
    Write-Host "   可用版本：$($Avail -join '、')" -ForegroundColor Yellow
    Write-Host "   不会自动改成别的版本。想装上面某个版本，请在「装了吗」里重新选一次。" -ForegroundColor Yellow
    exit 3
}}
Write-Host "✅ 版本检查通过：$Software $WantVersion 在包管理器里可用" -ForegroundColor Green
"""


def _pkg_cmd(install: dict, platform: str, version: str = "") -> str:
    if platform == "windows":
        wid = install.get("winget") or ""
        if wid:
            ver = f" --version {version}" if _is_pinned(version) else ""
            return (
                f"winget install --id {wid} --exact{ver}"
                f" --accept-source-agreements --accept-package-agreements"
            )
        if install.get("choco"):
            return f"choco install {install['choco']} -y"
        return "# Windows 无包管理器，请到官网下载安装包（见上方官方链接）"
    if platform == "macos":
        brew = install.get("brew") or ""
        if brew:
            return f"brew install {brew}"
        return "# macOS 建议先安装 Homebrew：/bin/bash -c \"$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
    pkg = install.get("apt") or install.get("yum") or ""
    if pkg:
        return (
            "if command -v apt-get >/dev/null 2>&1; then\n"
            f"    sudo apt-get update && sudo apt-get install -y {pkg}\n"
            "elif command -v yum >/dev/null 2>&1; then\n"
            f"    sudo yum install -y {install.get('yum') or pkg}\n"
            "else\n"
            "    echo '⚠️  未识别的包管理器，请手动安装'\n"
            "fi"
        )
    return "# Linux 请用系统包管理器安装"


def _env_block(install: dict, platform: str, sw: str) -> str:
    envs = install.get("env") or []
    if platform == "windows":
        bins = install.get("bin_paths") or []
        quoted = ", ".join("'" + b.replace("'", "''") + "'" for b in bins)
        exe = ((install.get("verify") or "").split() or [""])[0]
        lines = [
            "# ---------- 3. 环境变量（写用户级 PATH，不需要管理员） ----------",
            f"$BinCandidates = @({quoted})",
            "# 先刷新一次 PATH，后面的 find 命令才是新装的",
            "$env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' + [Environment]::GetEnvironmentVariable('Path', 'User')",
            "$BinDirs = @()",
            "foreach ($c in $BinCandidates) {",
            "    if (-not $c) { continue }",
            "    $hit = Get-Item -Path $c -ErrorAction SilentlyContinue | Select-Object -First 1",
            "    if ($hit) { $BinDirs += $hit.FullName }",
            "}",
            "if ($BinDirs.Count -gt 0) {",
            "    foreach ($d in $BinDirs) {",
            "        $UserPath = [Environment]::GetEnvironmentVariable('Path', 'User')",
            "        if (-not $UserPath) { $UserPath = '' }",
            "        if ($UserPath -notlike \"*$d*\") {",
            "            [Environment]::SetEnvironmentVariable('Path', ($UserPath.TrimEnd(';') + ';' + $d), 'User')",
            "            Write-Host \"✅ 已加入用户 PATH：$d\" -ForegroundColor Green",
            "        } else {",
            "            Write-Host \"ℹ️  用户 PATH 里已有：$d\" -ForegroundColor Yellow",
            "        }",
            "        $env:Path = $env:Path.TrimEnd(';') + ';' + $d",
            "    }",
            "} elseif (Get-Command '" + exe + "' -ErrorAction SilentlyContinue) {",
            f"    Write-Host '✅ {exe} 已经在 PATH 里（包管理器装的，不用手动加）' -ForegroundColor Green",
            "} else {",
            "    Write-Host '⚠️  没找到安装目录，请手动把 bin 目录加进 PATH：' -ForegroundColor Yellow",
        ]
        for e in envs:
            lines.append(f"    Write-Host '    - {e}' -ForegroundColor Yellow")
        lines.append("}")
        return "\n".join(lines)
    name_upper = re.sub(r"[^A-Za-z0-9]", "_", sw).upper()
    lines = [
        "# ---------- 3. 环境变量 ----------",
        "SHELL_RC=\"$HOME/.zshrc\"",
        "[ -n \"$BASH_VERSION\" ] && SHELL_RC=\"$HOME/.bashrc\"",
        "grep -q '装了吗' \"$SHELL_RC\" 2>/dev/null || {",
        f"    echo '' >> \"$SHELL_RC\"",
        f"    echo '# ---- 装了吗: {sw} ----' >> \"$SHELL_RC\"",
        f"    echo 'export {name_upper}_HOME=\"$HOME/.local/{sw.lower()}\"' >> \"$SHELL_RC\"",
        f"    echo 'export PATH=\"${name_upper}_HOME/bin:$PATH\"' >> \"$SHELL_RC\"",
        "}",
        f"echo 'ℹ️  已写入 $SHELL_RC，执行 source $SHELL_RC 生效'",
    ]
    for e in envs:
        lines.append(f"# - {e}")
    return "\n".join(lines)


def _verify_block(install: dict, platform: str) -> str:
    cmd = install.get("verify") or ""
    if platform == "windows":
        exe = (cmd.split() or ["cmd"])[0] if cmd else "cmd"
        checks = cmd if cmd else f"{exe} --version"
        return f"""# ---------- 4. 安装验证 ----------
Write-Host "`n🔍 验证安装结果：" -ForegroundColor Cyan
# 刷新一次 PATH，避免刚写入的目录在当前会话里不生效
$env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' + [Environment]::GetEnvironmentVariable('Path', 'User')
$Exe = Get-Command '{exe}' -ErrorAction SilentlyContinue
if (-not $Exe) {{
    Write-Host "⚠️  已安装，但当前终端还找不到 {exe} 命令" -ForegroundColor Yellow
    Write-Host "    PATH 已经写好了，请关掉这个窗口重新打开一个终端再试" -ForegroundColor Yellow
    exit 2
}}

# 绿色版软件（nginx / php / redis 这类）是按「自己所在目录」去找 conf/ 和 logs/ 的。
# winget 装完在 WinGet\\Links 下是个符号链接，在 C:\\WINDOWS\\system32 里跑必然报
#   CreateFile() ".../conf/nginx.conf" failed
# 所以先把链接还原成真实路径，进到那个目录里再执行检查。
$Real = $Exe.Source
$Item = Get-Item -LiteralPath $Real -ErrorAction SilentlyContinue
if ($Item -and $Item.Target) {{ $Real = ($Item.Target | Select-Object -First 1) }}
$BinDir = Split-Path $Real -Parent
Write-Host "   安装目录：$BinDir" -ForegroundColor DarkGray

Push-Location $BinDir
& cmd /c "{checks}"
$Check = $LASTEXITCODE
Pop-Location

if ($Check -ne 0) {{
    Write-Host "❌ 命令能跑，但自检没通过（配置或服务有问题），先按上面的提示修" -ForegroundColor Red
    exit 1
}}
Write-Host "`n🎉 装好了！今天你装了吗？装了！" -ForegroundColor Green"""
    return f"""# ---------- 4. 安装验证 ----------
echo ""
echo "🔍 验证安装结果："
{cmd} && {{
    echo ""
    echo "🎉 装好了！今天你装了吗？装了！"
}} || {{
    echo "😵 没装成功，往上翻翻报错信息"
    exit 1
}}"""


def local_template(software: dict, version: str, platform: str) -> str:
    name = software.get("name") or "未知软件"
    preset = find_preset(name) or {}
    install = preset.get("install") or {}
    lang = CODE_LANG.get(platform, "bash")
    is_link = (software.get("install_type") or preset.get("install_type")) == "link"
    official = software.get("official_url") or preset.get("official_url") or ""

    if platform == "windows":
        wid = install.get("winget") or ""
        if wid:
            detect = (
                f"$Listing = (winget list --id {wid} --exact 2>&1 | Out-String)\n"
                f"if ($Listing -match '{wid}') {{\n"
                f"    Write-Host '⚠️  已经装过这个包了，下面会尝试升级到可用版本' -ForegroundColor Yellow\n"
                f"}}"
            )
        else:
            detect = "Write-Host 'ℹ️  该软件没有 winget 包，走下面的安装方式' -ForegroundColor Yellow"
        script = "\n".join([
            _ps_header(name, version),
            detect,
            "",
            _version_gate(name, version, install),
            "",
            "# ---------- 2. 安装 ----------",
            _pkg_cmd(install, platform, version),
            '# 安装命令失败就停，不要带着失败继续往下走',
            '# 但「已装最新版」时 winget 会返回 -1978335189（0x8A150015 无可用升级），这不是失败',
            'if ($LASTEXITCODE -ne 0) {',
            '    if ($LASTEXITCODE -eq -1978335189) {',
            '        Write-Host "ℹ️  本机已经是这个版本，跳过安装" -ForegroundColor Yellow',
            '    } else {',
            '        Write-Host "❌ 安装失败（退出码 $LASTEXITCODE），请把上面的报错发给我们，或改用官方安装包" -ForegroundColor Red',
            '        exit $LASTEXITCODE',
            '    }',
            '}',
            "",
            _env_block(install, platform, name),
            "",
            _verify_block(install, platform),
        ])
    else:
        brew_check = ""
        if platform == "macos":
            brew_check = """if ! command -v brew >/dev/null 2>&1; then
    echo "🍺 没装 Homebrew，先装它："
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
fi
echo "✅ 包管理器就绪"
"""
        script = "\n".join([
            _bash_header(name, version, platform),
            brew_check if platform == "macos" else "echo '✅ 使用系统包管理器'",
            "",
            "# ---------- 2. 安装 ----------",
            _pkg_cmd(install, platform),
            "",
            _env_block(install, platform, name),
            "",
            _verify_block(install, platform),
        ])

    if is_link and official:
        link_sec = (
            f"这类软件有官方安装包，直接下载安装最省心 👇\n\n"
            f"- **官方下载页**：{official}\n"
            f"- **包管理器**（推荐，能自动升级）：`{_pkg_cmd(install, platform)}`\n"
        )
    elif official:
        link_sec = f"无强制官方安装包，命令行直接装即可；官网备查：{official}\n"
    else:
        link_sec = "无官方安装包，直接用下面的脚本装。\n"

    if platform == "windows":
        run_sec = (
            "1. 复制上面的脚本\n"
            "2. **开始菜单搜索 PowerShell → 右键 → 以管理员身份运行**\n"
            "3. 粘贴回车，看到 🎉 就成了\n"
            "4. 若提示『禁止运行脚本』，先执行：`Set-ExecutionPolicy -Scope Process RemoteSigned`\n"
        )
    else:
        run_sec = (
            "1. 把脚本存成 `install.sh`\n"
            "2. `chmod +x install.sh`\n"
            "3. `./install.sh`（涉及 /usr/local 等目录时脚本会要 sudo 密码）\n"
            "4. 执行 `source ~/.zshrc`（或 `~/.bashrc`）让环境变量生效\n"
        )

    notes = install.get("notes") or ["网络不通先检查代理/镜像源", "端口冲突改配置文件里的端口", "权限不足记得提权"]
    after = install.get("after") or ["重启终端验证一次", "确认版本符合预期"]
    verify_cmd = install.get("verify") or "--version"

    return f"""## 🎯 一句话

{name} {version} · {PLATFORM_CN.get(platform, platform)} 一键到位，装完就能跑。

## 🔗 官方安装包

{link_sec}

## 📦 一键安装脚本

```{lang}
{script}
```

## ▶️ 怎么运行

{run_sec}

## ⚙️ 环境变量

| 变量 | 值 | 说明 |
| --- | --- | --- |
| PATH | 软件 `bin` 目录 | 让命令行能直接调用 |
| {re.sub(r'[^A-Za-z0-9]', '_', name).upper()}_HOME | 软件安装根目录 | 供其它工具引用 |

{chr(10).join(f'- {e}' for e in (install.get('env') or ['按需把软件目录加进 PATH']))}

## ✅ 安装验证

```{lang}
{verify_cmd}
```

## 🩺 常见问题

{chr(10).join(f'{i}. {n}' for i, n in enumerate(notes[:5], 1))}

## 🚀 执行后建议

{chr(10).join(f'- {a}' for a in after[:5])}

---
> 🤖 本方案由「装了吗」本地模板生成（AI 未配置时自动降级）。今天你装了吗？

{TEMPLATE_MARK}
"""


def summarize(md: str) -> str:
    """取方案正文的第一句话做摘要。"""
    for line in md.splitlines():
        line = line.strip()
        if line and not line.startswith(("#", ">", "-", "|", "```")) and len(line) > 6:
            return line[:120]
    return "装了吗专属安装方案"


async def generate_plan_md(software: dict, version: str, platform: str,
                           timeout: int | None = None) -> tuple[str, str, str, str]:
    """返回 (markdown, summary, generated_by, official_url)。"""
    official = software.get("official_url") or ""
    try:
        md = await ai_generate_plan(software, version, platform, timeout=timeout)
        if md and "一键安装脚本" in md:
            return md, summarize(md), "ai", official
        if md:
            return md, summarize(md), "ai", official
        raise AIError("空内容")
    except Exception as e:  # noqa: BLE001
        logger.warning("AI 生成失败，降级本地模板：%s", e)
        md = local_template(software, version, platform)
        return md, summarize(md), "template", official
