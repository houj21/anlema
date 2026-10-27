import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  ArrowRight,
  Check,
  Copy,
  RefreshCw,
  Rocket,
  Search,
  Server,
  Settings2,
  Sparkles,
  ThumbsDown,
  ThumbsUp,
  Wrench,
  X,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card } from '@/components/ui/card'
import { MarkdownView } from '@/components/MarkdownView'
import { InstallConsole, type LogLine } from '@/components/InstallConsole'
import { api, extractScript, getApiBase, setApiBase, type Platform, type Plan, type Software } from '@/lib/api'
import { cn } from '@/lib/utils'

const PLATFORMS: { key: Platform; label: string; emoji: string }[] = [
  { key: 'windows', label: 'Windows', emoji: '🪟' },
  { key: 'macos', label: 'macOS', emoji: '🍎' },
  { key: 'linux', label: 'Linux', emoji: '🐧' },
]

const QUICK = [
  'MySQL', 'Node.js', 'Python', 'JDK', 'Git', 'Maven', 'Redis', 'Docker',
  'Nginx', 'Go', 'Rust', 'MongoDB', 'PostgreSQL', 'VS Code', 'IDEA', 'Homebrew', 'nvm',
]

const FUN_LOADING = [
  '正在摇人（AI）写方案…',
  '正在翻官方文档，别催…',
  '正在把坑提前踩一遍…',
  '正在检查命令有没有写错…',
  '快好了，就差一个环境变量…',
]

declare global {
  interface Window {
    zlm?: {
      info: () => Promise<{ platform: Platform; arch: string; version: string }>
      runScript: (p: { script: string; scriptType: string; elevate: boolean }) => Promise<{ ok: boolean; code?: number; error?: string }>
      stopScript: () => Promise<{ ok: boolean }>
      openExternal: (url: string) => Promise<{ ok: boolean }>
      onOutput: (cb: (d: LogLine) => void) => () => void
      onDone: (cb: (d: { code: number }) => void) => void
    }
  }
}

export default function App() {
  const [query, setQuery] = useState('')
  const [platform, setPlatform] = useState<Platform>('windows')
  const [software, setSoftware] = useState<Software | null>(null)
  const [versions, setVersions] = useState<string[]>([])
  const [version, setVersion] = useState('')
  const [versionSource, setVersionSource] = useState('')
  const [plan, setPlan] = useState<Plan | null>(null)
  const [loading, setLoading] = useState(false)
  const [loadingTip, setLoadingTip] = useState(FUN_LOADING[0])
  const [waited, setWaited] = useState(0)
  const [upgrading, setUpgrading] = useState(false)
  const [error, setError] = useState('')
  const [presets, setPresets] = useState<Software[]>([])
  const [aiEnabled, setAiEnabled] = useState<boolean | null>(null)

  const [logs, setLogs] = useState<LogLine[]>([])
  const [running, setRunning] = useState(false)
  const [showConsole, setShowConsole] = useState(false)
  const [elevate, setElevate] = useState(true)
  const [confirm, setConfirm] = useState(false)

  const [vote, setVote] = useState<'valid' | 'invalid' | null>(null)
  const [feedback, setFeedback] = useState('')
  const [showSettings, setShowSettings] = useState(false)
  const [baseInput, setBaseInput] = useState(getApiBase())
  const tipTimer = useRef<number | null>(null)

  /* ---------------- 初始化 ---------------- */
  useEffect(() => {
    api.softwares().then((r) => setPresets(r.items)).catch(() => setPresets([]))
    api.health().then((r) => setAiEnabled(r.ai_enabled)).catch(() => setAiEnabled(false))
    window.zlm?.info().then((i) => setPlatform(i.platform)).catch(() => {})
  }, [])

  useEffect(() => {
    const off1 = window.zlm?.onOutput((d) => setLogs((l) => [...l.slice(-500), d]))
    const off2 = window.zlm?.onDone(() => setRunning(false))
    return () => {
      off1?.()
      off2?.()
    }
  }, [])

  const startTip = useCallback(() => {
    let i = 0
    setWaited(0)
    if (tipTimer.current) window.clearInterval(tipTimer.current)
    tipTimer.current = window.setInterval(() => {
      i = (i + 1) % FUN_LOADING.length
      setLoadingTip(FUN_LOADING[i])
      // AI 出方案经常要好几分钟，把等待时长显示出来，别让人以为卡死了
      setWaited((w) => w + 1.6)
    }, 1600)
  }, [])

  const stopTip = useCallback(() => {
    if (tipTimer.current) {
      window.clearInterval(tipTimer.current)
      tipTimer.current = null
    }
  }, [])

  /* ---------------- 解析软件 ---------------- */
  const doResolve = async (q: string) => {
    const text = q.trim()
    if (!text) return
    setError('')
    setLoading(true)
    startTip()
    setPlan(null)
    setVote(null)
    try {
      const r = await api.resolve(text)
      setSoftware(r.software)
      const v = await api.versions(r.software.slug, false, platform)
      setVersions(v.versions.map((x) => x.version))
      setVersion(v.latest || v.versions[0]?.version || 'latest')
      setVersionSource(v.source)
      api.event({ software_name: r.software.name, version: '', platform, event_type: 'select' })
    } catch (e: any) {
      setError(`没搞定：${e.message}（服务起来了没？点右上角齿轮看看地址）`)
    } finally {
      setLoading(false)
      stopTip()
    }
  }

  const refreshVersions = async () => {
    if (!software) return
    setLoading(true)
    try {
      const v = await api.versions(software.slug, true, platform)
      setVersions(v.versions.map((x) => x.version))
      setVersion(v.latest || v.versions[0]?.version || 'latest')
      setVersionSource(v.source)
    } catch (e) {
      /* ignore */
    } finally {
      setLoading(false)
    }
  }

  /* ---------------- 生成方案 ---------------- */
  const doGenerate = async (force = false) => {
    if (!software) return
    setError('')
    setLoading(true)
    startTip()
    try {
      // fast：先秒出本地模板，AI 在后台写好会自动升级（AI 写长方案常要 2-5 分钟）
      const r = await api.generate(software.name, version, platform, force, true)
      setPlan(r.plan)
      setVote(null)
      if (r.plan?.generated_by === 'template') {
        waitForUpgrade(r.plan.id)
      }
    } catch (e: any) {
      setError(`生成失败：${e.message}`)
    } finally {
      setLoading(false)
      stopTip()
    }
  }

  // AI 后台升级完成后自动替换展示的内容（最多等 6 分钟）
  const waitForUpgrade = (planId: number) => {
    let tries = 0
    setUpgrading(true)
    const tick = window.setInterval(async () => {
      tries += 1
      if (tries > 72) {
        window.clearInterval(tick)
        setUpgrading(false)
        return
      }
      try {
        const p = await api.plan(planId)
        if (p.plan?.generated_by === 'ai') {
          window.clearInterval(tick)
          setUpgrading(false)
          setPlan(p.plan)
        }
      } catch {
        /* 忽略单次查询失败 */
      }
    }, 5000)
  }

  useEffect(() => {
    if (plan && platform) {
      // 平台切换后提示需要重新生成
    }
  }, [platform])

  /* ---------------- 一键安装 ---------------- */
  const script = useMemo(
    () => (plan ? extractScript(plan.content_md, plan.platform as Platform) : null),
    [plan]
  )

  // 点「一键安装」先弹确认框，确认后才真的跑，避免误点
  const askInstall = () => {
    if (!plan || !script) return
    setConfirm(true)
  }

  const doInstall = async () => {
    setConfirm(false)
    if (!plan || !script) return
    setShowConsole(true)
    setRunning(true)
    setLogs([{ text: `$ 装了吗 · 准备执行 ${plan.software_name} ${plan.version} 的安装脚本`, kind: 'sys' }])
    api.install(plan.id).catch(() => {})
    if (!window.zlm) {
      setLogs((l) => [...l, { text: '⚠️ 当前不在 Electron 里运行，请复制脚本手动执行～', kind: 'err' }])
      setRunning(false)
      return
    }
    const res = await window.zlm.runScript({
      script: script.code,
      scriptType: script.lang === 'powershell' ? 'powershell' : 'bash',
      elevate,
      // 用来核对「实际装上的版本」和「你要的版本」是否一致
      expectedVersion: plan.version,
    })
    if (res.error) {
      setLogs((l) => [...l, { text: `❌ ${res.error}`, kind: 'err' }])
    }
    setRunning(false)
  }

  const copyScript = async () => {
    if (!script) return
    try {
      await navigator.clipboard.writeText(script.code)
    } catch (e) {
      /* ignore */
    }
  }

  const sendVote = async (v: 'valid' | 'invalid') => {
    if (!plan) return
    setVote(v)
    await api.vote(plan.id, v, feedback)
    const p = await api.plan(plan.id)
    setPlan(p.plan)
  }

  const sendFeedback = async () => {
    if (!plan || !feedback.trim()) return
    await api.vote(plan.id, vote ?? 'none', feedback)
    setFeedback('')
    setError('')
    alert('收到！感谢反馈 🙌')
  }

  return (
    <div className="min-h-full">
      {/* 顶栏 */}
      <header className="sticky top-0 z-30 border-b-[3px] border-ink bg-paper/90 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-3">
          <div className="flex items-center gap-3">
            <div className="grid h-11 w-11 place-items-center rounded-xl border-[3px] border-ink bg-lime text-2xl shadow-stickerSm animate-wiggle">
              📦
            </div>
            <div>
              <h1 className="font-fun text-2xl leading-none">装了吗</h1>
              <p className="mt-1 font-mono text-[11px] text-ink/60">今天你装了吗？</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Badge tone={aiEnabled ? 'lime' : 'cream'} className="hidden sm:inline-flex">
              <Sparkles className="h-3 w-3" />
              {aiEnabled ? 'AI 在线' : '本地模板'}
            </Badge>
            <Button
              size="icon"
              variant="outline"
              title="服务端地址"
              onClick={() => {
                setBaseInput(getApiBase())
                setShowSettings(true)
              }}
            >
              <Settings2 className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-6 pb-24 pt-6">
        {/* 搜索 */}
        <Card className="animate-pop bg-gradient-to-br from-white to-cream">
          <div className="p-6">
            <label className="font-fun text-lg">你想装点啥？</label>
            <p className="mt-1 text-[13px] text-ink/60">
              一句话就行，比如「我想装 MySQL」——剩下的交给 AI。
            </p>
            <div className="mt-4 flex flex-col gap-3 sm:flex-row">
              <div className="relative flex-1">
                <Search className="pointer-events-none absolute left-4 top-1/2 h-5 w-5 -translate-y-1/2 text-ink/40" />
                <input
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && doResolve(query)}
                  placeholder="我想装 MySQL…"
                  className="h-13 w-full rounded-xl border-[3px] border-ink bg-white pl-12 pr-4 text-[15px] font-medium outline-none placeholder:text-ink/35 focus:bg-lime/10"
                />
              </div>
              <Button size="lg" variant="lime" disabled={loading} onClick={() => doResolve(query)}>
                {loading ? <RefreshCw className="h-4 w-4 animate-spin" /> : <Rocket className="h-4 w-4" />}
                {loading ? '搞定中' : '帮我装'}
              </Button>
            </div>

            <div className="mt-4 flex flex-wrap gap-2">
              {QUICK.map((q) => (
                <button
                  key={q}
                  onClick={() => {
                    setQuery(q)
                    doResolve(q)
                  }}
                  className="rounded-full border-2 border-ink bg-white px-3 py-1 text-[12.5px] font-bold shadow-stickerSm btn-pop hover:bg-lime"
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        </Card>

        {/* 加载提示 */}
        {loading && (
          <div className="mt-6 flex items-center gap-3 rounded-xl border-[3px] border-dashed border-ink bg-cyan/20 px-5 py-4">
            <Wrench className="h-5 w-5 animate-spin text-ink" />
            <div className="flex flex-col">
              <span className="font-fun">{loadingTip}</span>
              <span className="mt-0.5 font-mono text-[12px] text-ink/60">
                已等待 {Math.round(waited)} 秒{waited > 30 ? '（AI 写长方案比较慢，通常 1-3 分钟；超过 2.5 分钟会自动改用本地模板，不会一直卡着）' : ''}
              </span>
            </div>
          </div>
        )}

        {error && (
          <div className="mt-6 rounded-xl border-[3px] border-ink bg-pink/20 px-5 py-4 font-medium">
            😵 {error}
          </div>
        )}

        {/* 第二步：版本 + 平台 */}
        {software && (
          <Card className="mt-6 animate-slideUp">
            <div className="p-6">
              <div className="flex flex-wrap items-center gap-3">
                <span className="text-3xl">{software.icon || '📦'}</span>
                <div className="min-w-0">
                  <div className="font-fun text-xl">{software.name}</div>
                  {software.tagline && (
                    <div className="text-[13px] text-ink/60">{software.tagline}</div>
                  )}
                </div>
                <div className="ml-auto flex flex-wrap gap-2">
                  <Badge tone="cyan">{software.source_kind || 'manual'} 源</Badge>
                  {versionSource && (
                    <Badge tone="cream">
                      版本来源：{versionSource === 'winget' ? 'winget 仓库（本机能直接装）' : versionSource}
                    </Badge>
                  )}
                  {software.install_type === 'link' && <Badge tone="pink">官方安装包</Badge>}
                </div>
              </div>

              <div className="mt-5 grid gap-4 md:grid-cols-2">
                <div>
                  <div className="mb-2 flex items-center justify-between">
                    <span className="text-[13px] font-bold">选版本</span>
                    <button
                      onClick={refreshVersions}
                      className="inline-flex items-center gap-1 text-[12px] text-ink/60 hover:text-pink"
                    >
                      <RefreshCw className="h-3 w-3" /> 刷新版本列表
                    </button>
                  </div>
                  <select
                    value={version}
                    onChange={(e) => setVersion(e.target.value)}
                    className="h-11 w-full rounded-xl border-[3px] border-ink bg-white px-3 font-mono text-[14px] outline-none focus:bg-lime/10"
                  >
                    {versions.length === 0 && <option value="latest">latest</option>}
                    {versions.map((v) => (
                      <option key={v} value={v}>
                        {v}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <div className="mb-2 text-[13px] font-bold">选平台</div>
                  <div className="flex gap-2">
                    {PLATFORMS.map((p) => (
                      <button
                        key={p.key}
                        onClick={() => setPlatform(p.key)}
                        className={cn(
                          'flex-1 rounded-xl border-[3px] border-ink px-2 py-2 text-[13px] font-bold shadow-stickerSm btn-pop',
                          platform === p.key ? 'bg-lime' : 'bg-white hover:bg-cream'
                        )}
                      >
                        <span className="mr-1">{p.emoji}</span>
                        {p.label}
                      </button>
                    ))}
                  </div>
                </div>
              </div>

              <div className="mt-5 flex flex-wrap items-center gap-3">
                <Button variant="dark" onClick={() => doGenerate(false)} disabled={loading}>
                  <Sparkles className="h-4 w-4" /> 生成安装方案
                  <ArrowRight className="h-4 w-4" />
                </Button>
                {plan && (
                  <Button variant="outline" onClick={() => doGenerate(true)} disabled={loading}>
                    <RefreshCw className="h-4 w-4" /> 重新生成
                  </Button>
                )}
                {software.official_url && (
                  <Button
                    variant="outline"
                    onClick={() =>
                      window.zlm
                        ? window.zlm.openExternal(software.official_url)
                        : window.open(software.official_url, '_blank')
                    }
                  >
                    官网 <ArrowRight className="h-3.5 w-3.5" />
                  </Button>
                )}
              </div>
            </div>
          </Card>
        )}

        {/* 第三步：方案 */}
        {plan && (
          <Card className="mt-6 animate-slideUp">
            <div className="border-b-[3px] border-ink bg-cream px-6 py-4">
              <div className="flex flex-wrap items-center gap-2">
                <h2 className="font-fun text-xl">{plan.software_name} {plan.version}</h2>
                <Badge tone="dark">{PLATFORMS.find((p) => p.key === plan.platform)?.label}</Badge>
                <Badge tone={plan.generated_by === 'ai' ? 'lime' : 'cream'}>
                  {plan.generated_by === 'ai' ? 'AI 生成' : '本地模板'}
                </Badge>
                {upgrading && (
                  <Badge tone="cyan">
                    <Wrench className="h-3 w-3 animate-spin" /> AI 正在后台补充，写完自动替换
                  </Badge>
                )}
                <span className="ml-auto font-mono text-[12px] text-ink/50">
                  👀 {plan.view_count} · 🚀 {plan.install_count} · 👍 {plan.valid_count} · 👎{' '}
                  {plan.invalid_count}
                </span>
              </div>

              <div className="mt-4 flex flex-wrap items-center gap-3">
                <Button variant="lime" onClick={copyScript} disabled={!script}>
                  <Copy className="h-4 w-4" /> 复制脚本
                </Button>
                <Button variant="pink" onClick={askInstall} disabled={!script || running}>
                  <Rocket className="h-4 w-4" /> {running ? '正在装…' : '一键安装'}
                </Button>
                {script && (
                  <Badge tone="cream" title="实际会执行的脚本">
                    {script.code.split(/\r?\n/).length} 行脚本
                  </Badge>
                )}
                <label className="inline-flex cursor-pointer items-center gap-2 rounded-xl border-[3px] border-ink bg-white px-3 py-2 text-[13px] font-bold">
                  <input
                    type="checkbox"
                    checked={elevate}
                    onChange={(e) => setElevate(e.target.checked)}
                    className="h-4 w-4 accent-pink"
                  />
                  管理员/Sudo 模式
                </label>
                <div className="ml-auto flex items-center gap-2">
                  <Button
                    size="sm"
                    variant={vote === 'valid' ? 'lime' : 'outline'}
                    onClick={() => sendVote('valid')}
                  >
                    <ThumbsUp className="h-3.5 w-3.5" /> 有效
                  </Button>
                  <Button
                    size="sm"
                    variant={vote === 'invalid' ? 'pink' : 'outline'}
                    onClick={() => sendVote('invalid')}
                  >
                    <ThumbsDown className="h-3.5 w-3.5" /> 无效
                  </Button>
                </div>
              </div>

              {!script && (
                <p className="mt-3 text-[13px] text-pink">
                  这个方案没有可执行的脚本块（多半是官方安装包软件），请按正文里的链接下载安装。
                </p>
              )}
            </div>

            <div className="px-6 py-6">
              <MarkdownView content={plan.content_md} />
            </div>

            <div className="border-t-[3px] border-ink bg-paper2 px-6 py-4">
              <div className="font-fun">说点啥？（可选）</div>
              <div className="mt-2 flex flex-col gap-3 sm:flex-row">
                <input
                  value={feedback}
                  onChange={(e) => setFeedback(e.target.value)}
                  placeholder="例如：winget 装的时候报错 0x80070422"
                  className="h-11 flex-1 rounded-xl border-[3px] border-ink bg-white px-4 text-[14px] outline-none focus:bg-lime/10"
                />
                <Button variant="dark" onClick={sendFeedback}>
                  <Check className="h-4 w-4" /> 提交反馈
                </Button>
              </div>
            </div>
          </Card>
        )}

        {/* 空状态 */}
        {!software && !loading && (
          <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {presets.slice(0, 12).map((s) => (
              <button
                key={s.id}
                onClick={() => {
                  setQuery(s.name)
                  doResolve(s.name)
                }}
                className="sticker group p-4 text-left btn-pop hover:bg-lime"
              >
                <div className="text-2xl">{s.icon}</div>
                <div className="mt-2 font-fun">{s.name}</div>
                <div className="mt-1 line-clamp-2 text-[12.5px] text-ink/60">{s.tagline}</div>
              </button>
            ))}
          </div>
        )}

        {/* 安装前确认：看清楚要跑什么再点确认 */}
        {confirm && plan && script && (
          <div
            className="fixed inset-0 z-50 flex items-center justify-center bg-ink/50 p-6"
            onClick={() => setConfirm(false)}
          >
            <div
              data-testid="install-confirm"
              className="w-full max-w-2xl rounded-2xl border-[3px] border-ink bg-white p-6 shadow-[8px_8px_0_0_#111]"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="flex items-center gap-2">
                <Rocket className="h-5 w-5" />
                <h3 className="font-display text-[20px]">确认要执行吗？</h3>
              </div>
              <p className="mt-2 text-[14px] leading-6 text-ink/80">
                即将在本机用
                <Badge tone="cream">{script.lang === 'powershell' ? 'PowerShell' : 'Bash'}</Badge>
                执行
                <Badge tone="lime">
                  {plan.software_name} {plan.version}
                </Badge>
                的
                <Badge tone="pink">{script.code.split(/\r?\n/).length} 行脚本</Badge>
                {elevate && <Badge tone="cream">含管理员权限</Badge>}
                。执行过程不可撤销，脚本里的安装命令会真的改你的电脑。
              </p>

              <div className="mt-4 overflow-hidden rounded-xl border-[3px] border-ink bg-ink">
                <div className="flex items-center justify-between bg-ink px-3 py-1.5 text-[12px] font-bold text-white">
                  <span>脚本开头</span>
                  <span className="opacity-70">共 {script.code.split(/\r?\n/).length} 行</span>
                </div>
                <pre className="max-h-52 overflow-auto bg-cream p-3 font-mono text-[12px] leading-5 text-ink">
                  {script.code.split(/\r?\n/).slice(0, 5).join('\n')}
                  {'\n…'}
                </pre>
              </div>

              <div className="mt-5 flex items-center justify-end gap-3">
                <Button variant="default" onClick={() => setConfirm(false)}>
                  再想想
                </Button>
                <Button variant="pink" onClick={doInstall}>
                  <Rocket className="h-4 w-4" /> 确认执行
                </Button>
              </div>
            </div>
          </div>
        )}

        {/* 控制台：贴在视口底部，点了就能看见 */}
        {showConsole && (
          <div className="fixed inset-x-0 bottom-0 z-40 mx-auto max-w-6xl px-6 pb-4">
            <InstallConsole
              lines={logs}
              running={running}
              onStop={() => window.zlm?.stopScript()}
              onClear={() => setLogs([])}
              onClose={() => setShowConsole(false)}
            />
          </div>
        )}
      </main>

      {/* 设置弹层 */}
      {showSettings && (
        <div className="fixed inset-0 z-50 grid place-items-center bg-ink/50 p-6">
          <Card className="w-full max-w-md animate-pop">
            <div className="flex items-center justify-between border-b-[3px] border-ink px-5 py-3">
              <div className="flex items-center gap-2 font-fun">
                <Server className="h-4 w-4" /> 服务端地址
              </div>
              <button onClick={() => setShowSettings(false)}>
                <X className="h-4 w-4" />
              </button>
            </div>
            <div className="space-y-3 p-5">
              <input
                value={baseInput}
                onChange={(e) => setBaseInput(e.target.value)}
                className="h-11 w-full rounded-xl border-[3px] border-ink bg-white px-3 font-mono text-[13px] outline-none"
              />
              <p className="text-[12.5px] text-ink/60">
                安装版默认连线上服务。想连本机后端就填{' '}
                <code className="font-mono">http://127.0.0.1:8899</code>，记得先把服务端跑起来。
              </p>
              <Button
                variant="lime"
                className="w-full"
                onClick={() => {
                  setApiBase(baseInput)
                  setShowSettings(false)
                  api.health().then((r) => setAiEnabled(r.ai_enabled)).catch(() => setAiEnabled(false))
                }}
              >
                保存
              </Button>
            </div>
          </Card>
        </div>
      )}
    </div>
  )
}
