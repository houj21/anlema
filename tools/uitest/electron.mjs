/* 真实 Electron 窗口冒烟：验证「一键安装」执行链路（只跑无害脚本，不装真实软件）
 * 前置：desktop 已 npm run build，服务端 8899 已启动
 */
import { _electron as electron } from 'playwright'

const APP = new URL('../../desktop', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1')
const EXE = process.env.ELECTRON_PATH || `${APP}/node_modules/electron/dist/electron.exe`
const out = []
const log = (ok, name, extra = '') => {
  out.push(ok)
  console.log(`${ok ? '✅' : '❌'} ${name} ${extra}`)
}

const app = await electron.launch({ executablePath: EXE, args: [APP] })
const win = await app.firstWindow()

await win.waitForSelector('text=装了吗', { timeout: 30000 })
log(true, 'Electron 窗口加载完成', await win.title())

const info = await win.evaluate(() => window.zlm.info())
log(!!info?.platform, '主进程返回平台信息', info?.platform)

const isWin = info?.platform === 'windows'
const scriptText = isWin
  ? 'Write-Host "hello-装了吗"\nWrite-Host "第二行日志"\nexit 0'
  : '#!/usr/bin/env bash\necho "hello-装了吗"\necho "第二行日志"\nexit 0'

const run = await win.evaluate(async (payload) => {
  window.__lines = []
  const off = window.zlm.onOutput((d) => window.__lines.push(`${d.kind}|${d.text}`))
  const r = await window.zlm.runScript(payload)
  off()
  return { r, lines: window.__lines }
}, { script: scriptText, scriptType: isWin ? 'powershell' : 'bash', elevate: false })
log(run.r?.ok === true, '脚本执行成功（退出码 0）', `code=${run.r?.code}`)
log(run.lines.some((l) => l.includes('hello-装了吗')), '日志实时回传且中文正常')
log(run.lines.some((l) => l.includes('第二行日志')), '多行日志完整')

const badText = isWin ? 'Write-Host "故意失败"\nexit 3' : 'echo "故意失败"\nexit 3'
const bad = await win.evaluate(async (payload) => {
  window.__l2 = []
  const off = window.zlm.onOutput((d) => window.__l2.push(d.text))
  const r = await window.zlm.runScript(payload)
  off()
  return { r, lines: window.__l2 }
}, { script: badText, scriptType: isWin ? 'powershell' : 'bash', elevate: false })
log(bad.r?.ok === false && bad.r?.code === 3, '失败退出码被正确回传', `code=${bad.r?.code}`)

// 安全阀：脚本里写 ErrorActionPreference='Stop' + 原生命令失败时，PowerShell 会静默终止
// 且退出码为 0（"假成功"）。执行器会把它降级成 Continue，这里验证降级生效。
if (isWin) {
  const stopText =
    'Write-Host "stop-test-start"\n' +
    "$ErrorActionPreference = 'Stop'\n" +
    'winget show --id Definitely.Not.A.Real.Package --exact\n' +
    'Write-Host "stop-test-end"\n'
  const stopRun = await win.evaluate(async (payload) => {
    window.__l3 = []
    const off = window.zlm.onOutput((d) => window.__l3.push(d.text))
    const r = await window.zlm.runScript(payload)
    off()
    return { r, lines: window.__l3 }
  }, { script: stopText, scriptType: 'powershell', elevate: false })
  // 降级生效时脚本会继续跑完并打印 end（而不是静默断在 winget 那行）
  const continued = stopRun.lines.some((l) => l.includes('stop-test-end'))
  log(continued, 'Stop 被降级为 Continue（不再静默假成功）', `code=${stopRun.r?.code}`)
}

await win.getByPlaceholder('我想装 MySQL…').fill('MySQL')
await win.getByRole('button', { name: /帮我装/ }).click()
await win.waitForSelector('select', { timeout: 60000 })
await win.locator('select').selectOption('8.0.36')
await win.getByRole('button', { name: /生成安装方案/ }).click()
await win.waitForSelector('.md-body', { timeout: 180000 })
log((await win.locator('.md-body').innerText()).includes('一键安装脚本'), 'Electron 内完整走通：搜索 → 生成 → 渲染')

// 该方案里前两个代码块是「官方安装包」的 winget/choco 短命令，
// 必须挑中「一键安装脚本」小节里的完整脚本，而不是这几行短命令。
const badge = await win.locator('text=/\\d+ 行脚本/').first().innerText()
const lines = parseInt(badge, 10)
log(lines > 50, '挑中的是完整安装脚本而非快速命令片段', badge)

// 版本对不上要明说：选的 8.0.40，包里只有 8.4.9 —— 不能装完还说"装好了"
if (isWin) {
  const verRun = await win.evaluate(async (payload) => {
    window.__l4 = []
    const off = window.zlm.onOutput((d) => window.__l4.push(d.text))
    const r = await window.zlm.runScript(payload)
    off()
    return { r, lines: window.__l4 }
  }, {
    script: 'Write-Host "Found MySQL [Oracle.MySQL] Version 8.4.9"\nexit 0',
    scriptType: 'powershell',
    elevate: false,
    expectedVersion: '8.0.40',
  })
  const warned = verRun.lines.some((l) => l.includes('注意版本') && l.includes('8.4.9'))
  log(warned, '版本不一致时会明确提示', `actual=${verRun.r?.actualVersion}`)
}

// 版本不存在时必须直接拦下，绝不能"顺手装个最新版"
if (isWin) {
  const blockRun = await win.evaluate(async (payload) => {
    window.__l5 = []
    const off = window.zlm.onOutput((d) => window.__l5.push(d.text))
    const r = await window.zlm.runScript(payload)
    off()
    return { r, lines: window.__l5 }
  }, {
    script:
      'winget install --id Oracle.MySQL --exact --version 8.0.40 --accept-source-agreements\n' +
      'Write-Host "SHOULD-NOT-RUN"\n',
    scriptType: 'powershell',
    elevate: false,
    expectedVersion: '8.0.40',
  })
  const blocked =
    blockRun.r?.ok === false && !blockRun.lines.some((l) => l.includes('SHOULD-NOT-RUN'))
  log(blocked, '版本不存在时直接拦下，不执行脚本', `code=${blockRun.r?.code}`)
}

// 注意：不在这里点「一键安装」，否则会真的执行安装命令（日志面板位置在 run.mjs 里验）

await app.close()
const ok = out.filter(Boolean).length
console.log(`\n通过 ${ok}/${out.length}`)
process.exit(ok === out.length ? 0 : 1)
