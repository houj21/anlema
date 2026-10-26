/* 浏览器视角冒烟：桌面端（搜索→选版本→生成→复制→投票）+ 管理后台（登录→方案→反馈→统计）
 * 前置：node serve.mjs（5190 桌面端 / 5191 后台） + 服务端 8899 已启动
 */
import { chromium } from 'playwright'

const DESKTOP = process.env.DESKTOP_URL || 'http://127.0.0.1:5190/'
const ADMIN = process.env.ADMIN_URL || 'http://127.0.0.1:5191/'
const out = []
const log = (ok, name, extra = '') => {
  out.push(ok)
  console.log(`${ok ? '✅' : '❌'} ${name} ${extra}`)
}

const browser = await chromium.launch(
  process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {}
)

/* ---------- 桌面端 ---------- */
try {
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } })
  const errors = []
  page.on('pageerror', (e) => errors.push(String(e)))
  page.on('console', (m) => m.type() === 'error' && errors.push(m.text()))

  await page.goto(DESKTOP, { waitUntil: 'networkidle' })
  log(await page.getByText('装了吗').first().isVisible(), '桌面端加载')
  log(await page.getByText('今天你装了吗？').first().isVisible(), '口号展示')

  // 用服务端已缓存的组合，避免每次冒烟都等 AI 生成 3-5 分钟
  await page.getByPlaceholder('我想装 MySQL…').fill('我想装 MySQL')
  await page.getByRole('button', { name: /帮我装/ }).click()
  await page.waitForSelector('select', { timeout: 60000 })
  log((await page.locator('select option').count()) > 0, '解析出版本下拉')
  try {
    await page.locator('select').selectOption('8.0.36', { timeout: 5000 })
  } catch (e) {
    /* 下拉里没有该版本就用默认的 */
  }
  await page.getByRole('button', { name: /生成安装方案/ }).click()
  // AI 网关对长文本很慢（实测 200-330 秒），等待上限要留够
  await page.waitForSelector('.md-body', { timeout: 420000 })
  const mdText = await page.locator('.md-body').innerText()
  log(mdText.includes('一键安装脚本'), 'Markdown 渲染出方案')
  log(mdText.includes('常见问题'), '方案含常见问题')

  const copyBtn = page.locator('button', { hasText: /^复制$/ }).first()
  await copyBtn.click()
  await page.waitForTimeout(500)
  log(await page.locator('button', { hasText: /^已复制$/ }).first().isVisible(), '代码块复制有反馈')

  // 浏览器里没有 Electron，点「确认执行」后只会提示，不会真执行 —— 安全
  await page.getByRole('button', { name: /一键安装/ }).click()
  await page.waitForTimeout(400)
  log(await page.getByText('确认要执行吗？').isVisible(), '点一键安装先弹确认框，不会直接跑')

  const modal = page.getByTestId('install-confirm')
  const modalText = await modal.innerText()
  log(/\d+\s*行脚本/.test(modalText), '确认框显示脚本行数')
  const preview = (await modal.locator('pre').innerText()).split('\n')
  log(preview.length >= 6 && preview[5].includes('…'), '确认框显示脚本前 5 行 + 省略号', preview[0].slice(0, 40))

  // 取消：不应该出现日志面板
  await page.getByRole('button', { name: '再想想' }).click()
  await page.waitForTimeout(400)
  log(!(await page.locator('text=安装现场直播').first().isVisible().catch(() => false)), '点取消后不会执行')

  // 确认：才出现日志面板（浏览器里提示「不在 Electron 里运行」）
  await page.getByRole('button', { name: /一键安装/ }).click()
  await page.waitForTimeout(300)
  await page.getByRole('button', { name: /确认执行/ }).click()
  await page.waitForTimeout(600)
  const panel = page.locator('text=安装现场直播').first()
  log(await panel.isVisible(), '确认后才唤起日志面板')
  const box = await panel.boundingBox()
  const vh = await page.evaluate(() => window.innerHeight)
  log(!!box && box.y > 0 && box.y < vh, '日志面板出现在当前视口内（不是页面最底部）', `y=${Math.round(box?.y ?? -1)} vh=${vh}`)

  const realErr = errors.filter((e) => !/favicon/i.test(e))
  log(realErr.length === 0, '桌面端无 JS 报错', realErr.slice(0, 2).join(' | '))
  await page.close()
} catch (e) {
  log(false, '桌面端流程异常', String(e).slice(0, 200))
}

/* ---------- 管理后台 ---------- */
try {
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } })
  const errors = []
  page.on('pageerror', (e) => errors.push(String(e)))
  page.on('console', (m) => m.type() === 'error' && errors.push(m.text()))

  await page.goto(ADMIN, { waitUntil: 'networkidle' })
  log(await page.getByText('装了吗 · 后台').first().isVisible(), '后台登录页加载')

  await page.getByPlaceholder('管理口令').fill('nope')
  await page.getByRole('button', { name: /进入后台/ }).click()
  await page.waitForTimeout(800)
  log(await page.getByText(/口令不对/).isVisible(), '错口令有提示')

  await page.getByPlaceholder('管理口令').fill(process.env.ADMIN_PASSWORD || 'zhuanglma')
  await page.getByRole('button', { name: /进入后台/ }).click()
  await page.waitForSelector('table', { timeout: 20000 })
  errors.length = 0 // 上面故意输错口令会产生一条 401
  log(true, '登录进入后台')

  await page.getByRole('button', { name: /编辑/ }).first().click()
  await page.waitForSelector('textarea', { timeout: 10000 })
  log(await page.locator('textarea').first().isVisible(), '方案编辑弹窗可打开')
  await page.getByRole('button', { name: '取消' }).click()

  await page.getByRole('button', { name: /用户反馈/ }).click()
  await page.waitForTimeout(700)
  log((await page.locator('body').innerText()).length > 100, '反馈页渲染')

  await page.getByRole('button', { name: /数据统计/ }).click()
  await page.waitForTimeout(700)
  log(await page.getByText(/软件被选次数/).isVisible(), '统计页渲染')

  const realErr = errors.filter((e) => !/favicon/i.test(e))
  log(realErr.length === 0, '后台无 JS 报错', realErr.slice(0, 2).join(' | '))
  await page.close()
} catch (e) {
  log(false, '后台流程异常', String(e).slice(0, 200))
}

await browser.close()
const ok = out.filter(Boolean).length
console.log(`\n通过 ${ok}/${out.length}`)
process.exit(ok === out.length ? 0 : 1)
