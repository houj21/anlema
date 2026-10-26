/* 装了吗 · Electron 主进程：负责窗口 + 本地执行安装脚本 */
const { app, BrowserWindow, ipcMain, shell, dialog } = require('electron')
const path = require('node:path')
const fs = require('node:fs')
const os = require('node:os')
const { spawn, spawnSync } = require('node:child_process')

const DEV_URL = 'http://127.0.0.1:5173'
let mainWindow = null
let currentProc = null
let tailTimer = null

const DEV_MODE = process.argv.includes('--dev') || process.env.ZLM_DEV === '1'

function isDev() {
  return !app.isPackaged && DEV_MODE
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1180,
    height: 820,
    minWidth: 940,
    minHeight: 640,
    title: '装了吗 · 今天你装了吗？',
    backgroundColor: '#FFF6E5',
    webPreferences: {
      preload: path.join(__dirname, 'preload.cjs'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  })

  const distIndex = path.join(__dirname, '..', 'dist', 'index.html')
  if (isDev()) {
    mainWindow.loadURL(DEV_URL)
  } else if (fs.existsSync(distIndex)) {
    mainWindow.loadFile(distIndex)
  } else {
    // 还没构建过：退回到 dev server（若已启动）
    mainWindow.loadURL(DEV_URL).catch(() => {
      mainWindow.loadFile(path.join(__dirname, '..', 'public', 'loading.html'))
    })
  }

  mainWindow.on('closed', () => {
    mainWindow = null
  })
}

app.whenReady().then(createWindow)
app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit()
})
app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) createWindow()
})

/* ---------------------- 脚本执行 ---------------------- */

function emit(channel, payload) {
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.webContents.send(channel, payload)
  }
}

// 本次执行的输出缓存：用于「退出码 0 但其实失败了」的兜底判定
let outBuffer = []

function pushLine(text, kind = 'out') {
  const lines = String(text).split(/\r?\n/)
  for (const l of lines) {
    if (l.trim() === '' && kind === 'out') continue
    outBuffer.push(l)
    if (outBuffer.length > 400) outBuffer.shift()
    emit('script:output', { text: l, kind })
  }
}

// 这些关键字出现时，基本可以断定没装成功（AI 脚本偶尔会把错误吞掉还 exit 0）
const FAIL_PATTERNS = [
  /No package found matching input criteria/i,
  /无法将.+项识别为/i,
  /is not recognized as the name of a cmdlet/i,
  /command not found/i,
  /不是内部或外部命令/,
  // nginx / 配置文件类自检失败（脚本常常打印了错误却 exit 0）
  /configuration file .* test failed/i,
  /could not open error log file/i,
  /^.*\[emerg\]/i,
  /配置语法检查失败/,
  /自检没通过/,
]

function findSuspicious() {
  return outBuffer.find((l) => FAIL_PATTERNS.some((re) => re.test(l)))
}

// 从输出里抠出「实际装上的版本」：winget 打 "Version 8.4.9"，程序自己打 "Ver 8.0.44"
const VERSION_PATTERNS = [/Version\s+(\d+\.\d+(?:\.\d+)?)/i, /\bVer\s+(\d+\.\d+\.\d+)/i]

function findInstalledVersion() {
  for (const line of outBuffer) {
    for (const re of VERSION_PATTERNS) {
      const m = re.exec(line)
      if (m) return m[1]
    }
  }
  return null
}

/** 8.0.36 和 8.0.44 也算不一致（小版本不同就要提示） */
function isVersionMismatch(expected, actual) {
  if (!expected || !actual) return false
  const e = String(expected).trim().toLowerCase()
  if (e === 'latest' || e === 'stable') return false
  return !actual.startsWith(e) && !e.startsWith(actual)
}

/** 能不能当具体版本用 */
function isPinnedVersion(v) {
  const s = String(v || '').trim().toLowerCase()
  if (!s || ['latest', 'stable', 'lts', 'current'].includes(s)) return false
  return /^\d+(\.\d+)*/.test(s)
}

// 脚本里可能出现很多 winget 包，只取 install 行上的
function findWingetInstallId(script) {
  const m = /winget\s+install\b[^\r\n]*?--id\s+([A-Za-z0-9._\-]+)/i.exec(script || '')
  return m ? m[1] : null
}

/**
 * 安装前本地预检：winget 仓库里没有用户选的版本，就直接拒绝执行，
 * 免得脚本"好心"装上最新版（用户要 8.0.x 却装了 8.4.x）。
 * @returns {string|null} 拦截原因，null 表示放行
 */
function preflightVersionCheck(script, expectedVersion) {
  if (process.platform !== 'win32') return null
  if (!isPinnedVersion(expectedVersion)) return null
  const pkgId = findWingetInstallId(script)
  if (!pkgId) return null
  try {
    const r = spawnSync('winget', ['show', '--id', pkgId, '--exact', '--versions'], {
      encoding: 'utf8',
      timeout: 30000,
      windowsHide: true,
    })
    const out = `${r.stdout || ''}`
    const versions = out
      .split(/\r?\n/)
      .map((l) => l.trim())
      .filter((l) => /^\d+(\.\d+)+$/.test(l))
    if (!versions.length) return null // 查不到就不拦，交给脚本自己判断
    if (versions.includes(String(expectedVersion).trim())) return null
    const hint =
      `包里没有 ${expectedVersion} 这个版本，已拦下，没有安装任何东西。\n` +
      `   可选版本：${versions.join('、')}\n` +
      `   请回到方案里换一个能装的版本再点「一键安装」。`
    pushLine(`❌ ${pkgId} ${hint}`, 'err')
    return hint
  } catch (e) {
    return null
  }
}

function writeScript(content, ext) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'zlm-'))
  const file = path.join(dir, `install.${ext}`)
  if (ext === 'ps1') {
    // PowerShell 5.1 默认按 ANSI 读取无 BOM 的脚本 → 中文全乱。
    // 1) 写 UTF-8 BOM  2) 脚本开头强制 UTF-8 输出，保证日志回传不乱码
    const header =
      '$OutputEncoding = [System.Text.Encoding]::UTF8\n' +
      '[Console]::OutputEncoding = [System.Text.Encoding]::UTF8\n' +
      '$env:PYTHONIOENCODING = "utf-8"\n'
    // 安全阀：winget/choco 是原生命令，在 ErrorActionPreference='Stop' 下失败会
    // 直接终止脚本且退出码为 0（用户看到"装好了"其实啥也没装）。统一降级为 Continue，
    // 由脚本自己检查 $LASTEXITCODE。
    const safe = content.replace(
      /\$ErrorActionPreference\s*=\s*(['"])Stop\1/gi,
      "$ErrorActionPreference = 'Continue'"
    )
    fs.writeFileSync(file, '\uFEFF' + header + safe, 'utf8')
  } else {
    fs.writeFileSync(file, content, 'utf8')
  }
  return file
}

/** 日志解码：优先 UTF-8，出现替换字符时回退 GBK */
function decodeBuf(buf) {
  const utf8 = buf.toString('utf8')
  if (!utf8.includes('\uFFFD')) return utf8
  try {
    return new TextDecoder('gbk').decode(buf)
  } catch (e) {
    return utf8
  }
}

function tailFile(file, proc) {
  let pos = 0
  tailTimer = setInterval(() => {
    try {
      if (!fs.existsSync(file)) return
      const text = decodeBuf(fs.readFileSync(file))
      if (text.length > pos) {
        pushLine(text.slice(pos))
        pos = text.length
      }
    } catch (e) {
      /* ignore */
    }
    if (proc && proc.killed) {
      clearInterval(tailTimer)
      tailTimer = null
    }
  }, 400)
}

function stopTail() {
  if (tailTimer) {
    clearInterval(tailTimer)
    tailTimer = null
  }
}

function runElevatedWindows(scriptPath) {
  const dir = path.dirname(scriptPath)
  const out = path.join(dir, 'run.out.log')
  fs.writeFileSync(out, '', 'utf8')

  // Start-Process -Verb RunAs 不能和 -RedirectStandardOutput 同用，Tee-Object 在 PS5.1
  // 又默认写 UTF-16；所以用一个 runner 脚本，靠 StreamWriter(UTF-8, AutoFlush) 实时落盘。
  const runner = path.join(dir, 'runner.ps1')
  const body = [
    '$ErrorActionPreference = "Continue"',
    `$log = "${out}"`,
    '$sw = New-Object System.IO.StreamWriter($log, $false, (New-Object System.Text.UTF8Encoding($false)))',
    '$sw.AutoFlush = $true',
    'try {',
    `  & "${scriptPath}" *>&1 | ForEach-Object { $sw.WriteLine($_) }`,
    '} catch {',
    '  $sw.WriteLine("❌ " + $_.Exception.Message)',
    '} finally {',
    '  $sw.Close()',
    '}',
  ].join('\n')
  fs.writeFileSync(runner, '\uFEFF' + body, 'utf8')

  const psCmd =
    'Start-Process -FilePath "powershell" ' +
    `-ArgumentList @('-NoProfile','-ExecutionPolicy','Bypass','-File','${runner}') ` +
    '-Verb RunAs -Wait'
  const proc = spawn('powershell', ['-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', psCmd], {
    windowsHide: true,
  })
  pushLine('🔐 已请求管理员权限，请在 UAC 弹窗里点「是」…', 'sys')
  tailFile(out, proc)
  return proc
}

function runElevatedMac(scriptPath) {
  const out = scriptPath.replace(/\.sh$/, '.out.log')
  fs.writeFileSync(out, '', 'utf8')
  const cmd = `do shell script "bash '${scriptPath}' > '${out}' 2>&1" with administrator privileges`
  const proc = spawn('osascript', ['-e', cmd])
  pushLine('🔐 已请求管理员权限，请输入系统密码...', 'sys')
  tailFile(out, proc)
  return proc
}

function runElevatedLinux(scriptPath) {
  const out = scriptPath.replace(/\.sh$/, '.out.log')
  fs.writeFileSync(out, '', 'utf8')
  const proc = spawn('bash', ['-c', `pkexec bash '${scriptPath}' > '${out}' 2>&1 || bash '${scriptPath}' > '${out}' 2>&1`])
  tailFile(out, proc)
  return proc
}

ipcMain.handle('script:run', async (_e, { script, scriptType, elevate, expectedVersion }) => {
  if (currentProc) {
    return { ok: false, error: '已经有一个安装任务在跑了' }
  }
  const platform = process.platform // win32 / darwin / linux
  const isWin = platform === 'win32'
  const ext = isWin || scriptType === 'powershell' ? 'ps1' : 'sh'
  let scriptPath
  try {
    scriptPath = writeScript(script, ext)
  } catch (e) {
    return { ok: false, error: `写临时脚本失败：${e.message}` }
  }

  outBuffer = []
  emit('script:output', { text: `$ 装了吗 · 脚本已就绪：${scriptPath}`, kind: 'sys' })

  // 最后一道闸：脚本说什么都不管，先在本地确认 winget 真有这个版本
  const blocked = preflightVersionCheck(script, expectedVersion)
  if (blocked) {
    emit('script:done', { code: 3 })
    return { ok: false, code: 3, error: blocked.split('\n')[0] }
  }

  let proc
  if (elevate) {
    proc = isWin
      ? runElevatedWindows(scriptPath)
      : platform === 'darwin'
        ? runElevatedMac(scriptPath)
        : runElevatedLinux(scriptPath)
  } else if (isWin || ext === 'ps1') {
    proc = spawn(
      'powershell',
      ['-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', scriptPath],
      { windowsHide: false }
    )
  } else {
    proc = spawn('bash', [scriptPath])
  }

  currentProc = proc

  // 提权模式下这些是「启动器」自己的输出（例如用户点了 UAC 的「否」），也要显示出来
  proc.stdout.on('data', (d) => pushLine(decodeBuf(d), 'out'))
  proc.stderr.on('data', (d) => pushLine(decodeBuf(d), 'err'))

  return await new Promise((resolve) => {
    proc.on('error', (err) => {
      stopTail()
      currentProc = null
      pushLine(`❌ 启动失败：${err.message}`, 'err')
      resolve({ ok: false, error: err.message })
    })
    proc.on('close', (code) => {
      stopTail()
      currentProc = null
      const suspicious = code === 0 ? findSuspicious() : null
      if (suspicious) {
        // 退出码 0 不代表成功：脚本可能把错误吞了
        pushLine('⚠️ 退出码是 0，但日志里出现了报错，实际很可能没装成功。', 'err')
        pushLine(`   可疑输出：${suspicious.slice(0, 160)}`, 'err')
        pushLine('   建议：把这段报错发给管理员，或改用方案里「官方安装包」的链接手动装。', 'err')
        emit('script:done', { code })
        resolve({ ok: false, code, error: '退出码 0，但日志中有报错，可能未真正安装成功' })
        return
      }
      // 已装过的软件再点一次，winget 会走「升级」分支，说清楚免得误会
      if (outBuffer.some((l) => /Found an existing package already installed/i.test(l))) {
        pushLine('ℹ️ 本机已经装过这个软件，这次是升级操作。', 'sys')
      }

      // 版本对不上要明说：用户选了 8.0.40，包管理器只有 8.4.9 时不能装完还说"装好了"
      const actual = findInstalledVersion()
      if (code === 0 && isVersionMismatch(expectedVersion, actual)) {
        pushLine(
          `⚠️ 注意版本：你要的是 ${expectedVersion}，实际装上的是 ${actual}。`,
          'err'
        )
        pushLine('   包管理器里没有你要的那个版本，只会给它能提供的最新版。', 'sys')
      }

      pushLine(
        code === 0 ? `✅ 执行结束（退出码 0）今天你装了吗？装了！` : `⚠️ 执行结束，退出码 ${code}`,
        code === 0 ? 'ok' : 'err'
      )
      emit('script:done', { code })
      resolve({ ok: code === 0, code, actualVersion: actual })
    })
  })
})

ipcMain.handle('script:stop', async () => {
  if (!currentProc) return { ok: false }
  try {
    if (process.platform === 'win32') {
      spawn('taskkill', ['/pid', String(currentProc.pid), '/f', '/t'])
    } else {
      process.kill(-currentProc.pid)
    }
    currentProc.kill()
  } catch (e) {
    /* ignore */
  }
  stopTail()
  currentProc = null
  pushLine('🛑 已手动停止', 'sys')
  return { ok: true }
})

ipcMain.handle('app:info', async () => {
  const p = process.platform
  return {
    platform: p === 'win32' ? 'windows' : p === 'darwin' ? 'macos' : 'linux',
    arch: process.arch,
    version: app.getVersion(),
  }
})

ipcMain.handle('app:openExternal', async (_e, url) => {
  await shell.openExternal(url)
  return { ok: true }
})

ipcMain.handle('app:pickSave', async () => {
  if (!mainWindow) return { ok: false }
  const res = await dialog.showSaveDialog(mainWindow, {
    defaultPath: 'install.sh',
    filters: [{ name: '安装脚本', extensions: ['sh', 'ps1'] }],
  })
  return { ok: !res.canceled, path: res.filePath }
})
