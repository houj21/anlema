import { useCallback, useEffect, useMemo, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import {
  BarChart3,
  Eye,
  LayoutDashboard,
  Loader2,
  LogOut,
  MessageSquare,
  PenLine,
  RefreshCw,
  Search,
  Server,
  Settings,
  Sparkles,
  Trash2,
  X,
} from 'lucide-react'
import { Badge, Button, Card, Input, Textarea } from '@/components/ui'
import { BarList } from '@/components/Bar'
import {
  api,
  clearToken,
  getBase,
  getToken,
  setBase,
  setToken,
  type Feedback,
  type Plan,
  type Stats,
} from '@/lib/api'
import { cn } from '@/lib/utils'

type Tab = 'plans' | 'feedbacks' | 'stats'

/** 后端地址设置：部署到线上后，页面要连哪个服务端就在这里填 */
function ServerDialog({ onClose }: { onClose: () => void }) {
  const [v, setV] = useState(getBase())
  const [msg, setMsg] = useState('')
  const [testing, setTesting] = useState(false)

  const test = async () => {
    setTesting(true)
    setMsg('')
    try {
      const res = await fetch(`${v.trim().replace(/\/+$/, '')}/api/health`)
      const j = await res.json()
      setMsg(j.ok ? `✅ 连上了（AI ${j.ai_enabled ? '在线' : '未启用'}）` : '❌ 地址能访问，但返回的不是装了吗的服务端')
    } catch {
      setMsg('❌ 连不上。检查：地址对不对、服务端有没有起、HTTPS 页面访问 http 地址会被浏览器拦')
    } finally {
      setTesting(false)
    }
  }

  const save = () => {
    setBase(v)
    location.reload()
  }

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-ink/40 p-6" onClick={onClose}>
      <div className="w-full max-w-md" onClick={(e) => e.stopPropagation()}>
        <Card className="animate-pop">
          <div className="border-b-[3px] border-ink bg-cream px-6 py-4">
            <div className="font-fun text-lg">服务端地址</div>
            <div className="font-mono text-[11.5px] text-ink/55">
              线上页面读不到数据时，把后端地址填在这里
            </div>
          </div>
          <div className="space-y-3 p-6">
            <Input value={v} placeholder="例如 http://1.2.3.4:8899" onChange={(e) => setV(e.target.value)} />
            {msg && <div className="text-[13px]">{msg}</div>}
            <div className="flex gap-2">
              <Button variant="outline" className="flex-1" onClick={test} disabled={testing || !v.trim()}>
                {testing ? <Loader2 className="h-4 w-4 animate-spin" /> : <Server className="h-4 w-4" />} 测试连接
              </Button>
              <Button variant="lime" className="flex-1" onClick={save}>
                保存并刷新
              </Button>
            </div>
            <div className="font-mono text-[11.5px] leading-relaxed text-ink/45">
              留空则回到默认 http://127.0.0.1:8899（只有本机能用）。
              <br />
              也可以在网址后面加 ?api=http://1.2.3.4:8899 直接指定。
            </div>
          </div>
        </Card>
      </div>
    </div>
  )
}

function Login({ onOk, onOpenServer }: { onOk: () => void; onOpenServer: () => void }) {
  const [pwd, setPwd] = useState('')
  const [err, setErr] = useState('')
  const [loading, setLoading] = useState(false)

  const submit = async () => {
    setLoading(true)
    setErr('')
    try {
      const r = await api.login(pwd)
      setToken(r.token)
      onOk()
    } catch (e: any) {
      setErr('口令不对哦，默认口令是 zhuanglma')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="grid min-h-full place-items-center p-6">
      <Card className="w-full max-w-sm animate-pop">
        <div className="border-b-[3px] border-ink bg-cream px-6 py-5 text-center">
          <div className="text-4xl">📦</div>
          <div className="mt-2 font-fun text-2xl">装了吗 · 后台</div>
          <div className="font-mono text-[12px] text-ink/60">今天你装了吗？</div>
        </div>
        <div className="space-y-3 p-6">
          <Input
            type="password"
            value={pwd}
            placeholder="管理口令"
            onChange={(e) => setPwd(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && submit()}
          />
          {err && <div className="text-[13px] text-pink">{err}</div>}
          <Button variant="lime" className="w-full" onClick={submit} disabled={loading}>
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : null} 进入后台
          </Button>
          <div className="text-center font-mono text-[11.5px] text-ink/45">
            默认口令 zhuanglma（可在 server/.env 改 ADMIN_PASSWORD）
          </div>
          <button
            onClick={onOpenServer}
            className="mx-auto flex items-center gap-1.5 font-mono text-[11.5px] text-ink/55 underline decoration-dotted hover:text-ink"
          >
            <Settings className="h-3 w-3" /> 服务端地址：{getBase() || '同源'}
          </button>
        </div>
      </Card>
    </div>
  )
}

function PlanEditor({ plan, onClose, onSaved }: { plan: Plan; onClose: () => void; onSaved: () => void }) {
  const [content, setContent] = useState(plan.content_md)
  const [title, setTitle] = useState(plan.title)
  const [summary, setSummary] = useState(plan.summary)
  const [saving, setSaving] = useState(false)
  const [regen, setRegen] = useState(false)
  const [preview, setPreview] = useState(false)

  const save = async () => {
    setSaving(true)
    try {
      await api.updatePlan(plan.id, { content_md: content, title, summary })
      onSaved()
      onClose()
    } finally {
      setSaving(false)
    }
  }

  const regenerate = async () => {
    setRegen(true)
    try {
      const r = await api.regenerate(plan.id)
      setContent(r.plan.content_md)
      setSummary(r.plan.summary)
    } finally {
      setRegen(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-ink/55 p-6">
      <Card className="flex max-h-[88vh] w-full max-w-4xl animate-pop flex-col">
        <div className="flex items-center justify-between border-b-[3px] border-ink px-5 py-3">
          <div className="flex items-center gap-2 font-fun">
            <PenLine className="h-4 w-4" /> 编辑方案 #{plan.id} · {plan.software_name} {plan.version}
          </div>
          <button onClick={onClose}>
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="grid min-h-0 flex-1 gap-4 overflow-auto p-5 md:grid-cols-2">
          <div className="flex flex-col gap-3">
            <Input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="标题" />
            <Input value={summary} onChange={(e) => setSummary(e.target.value)} placeholder="摘要" />
            <div className="flex items-center gap-2">
              <Button size="sm" variant={preview ? 'dark' : 'outline'} onClick={() => setPreview((v) => !v)}>
                <Eye className="h-3.5 w-3.5" /> {preview ? '编辑' : '预览'}
              </Button>
              <Button size="sm" variant="cyan" onClick={regenerate} disabled={regen}>
                {regen ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Sparkles className="h-3.5 w-3.5" />}
                AI 重新生成
              </Button>
            </div>
            <Textarea
              className="min-h-[46vh] flex-1 font-mono text-[12.5px]"
              value={content}
              onChange={(e) => setContent(e.target.value)}
            />
          </div>
          <div className="min-h-0 overflow-auto rounded-xl border-[3px] border-ink bg-paper p-4">
            <div className="md-body">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
            </div>
          </div>
        </div>
        <div className="flex justify-end gap-3 border-t-[3px] border-ink px-5 py-3">
          <Button variant="outline" onClick={onClose}>
            取消
          </Button>
          <Button variant="lime" onClick={save} disabled={saving}>
            保存
          </Button>
        </div>
      </Card>
    </div>
  )
}

export default function App() {
  const [token, setTok] = useState(getToken())
  const [showServer, setShowServer] = useState(false)
  const [tab, setTab] = useState<Tab>('plans')
  const [plans, setPlans] = useState<Plan[]>([])
  const [feedbacks, setFeedbacks] = useState<Feedback[]>([])
  const [stats, setStats] = useState<Stats | null>(null)
  const [q, setQ] = useState('')
  const [loading, setLoading] = useState(false)
  const [editing, setEditing] = useState<Plan | null>(null)
  const [aiEnabled, setAiEnabled] = useState(false)
  const [filterStatus, setFilterStatus] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [p, f, s] = await Promise.all([api.plans(), api.feedbacks(), api.stats()])
      setPlans(p.items)
      setFeedbacks(f.items)
      setStats(s)
    } catch (e) {
      clearToken()
      setTok('')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    if (token) load()
    api.health().then((r) => setAiEnabled(r.ai_enabled)).catch(() => {})
  }, [token, load])

  const filteredPlans = useMemo(() => {
    const k = q.trim().toLowerCase()
    if (!k) return plans
    return plans.filter(
      (p) =>
        p.software_name.toLowerCase().includes(k) ||
        p.version.toLowerCase().includes(k) ||
        p.platform.toLowerCase().includes(k)
    )
  }, [plans, q])

  const filteredFb = useMemo(
    () => (filterStatus ? feedbacks.filter((f) => f.status === filterStatus) : feedbacks),
    [feedbacks, filterStatus]
  )

  if (!token)
    return (
      <>
        <Login onOk={() => setTok(getToken())} onOpenServer={() => setShowServer(true)} />
        {showServer && <ServerDialog onClose={() => setShowServer(false)} />}
      </>
    )

  const tabs: { key: Tab; label: string; icon: any }[] = [
    { key: 'plans', label: '方案管理', icon: LayoutDashboard },
    { key: 'feedbacks', label: '用户反馈', icon: MessageSquare },
    { key: 'stats', label: '数据统计', icon: BarChart3 },
  ]

  return (
    <div className="min-h-full">
      <header className="sticky top-0 z-30 border-b-[3px] border-ink bg-paper/90 backdrop-blur">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-3">
          <div className="flex items-center gap-3">
            <span className="text-2xl">📦</span>
            <div>
              <div className="font-fun text-xl leading-none">装了吗 · 后台</div>
              <div className="font-mono text-[11px] text-ink/55">今天你装了吗？</div>
            </div>
            <Badge tone={aiEnabled ? 'lime' : 'cream'}>
              <Sparkles className="h-3 w-3" /> {aiEnabled ? 'AI 在线' : '本地模板'}
            </Badge>
          </div>
          <div className="flex items-center gap-2">
            <Button size="sm" variant="ghost" onClick={() => setShowServer(true)}>
              <Settings className="h-3.5 w-3.5" /> 服务端地址
            </Button>
            <Button size="sm" variant="outline" onClick={load} disabled={loading}>
              <RefreshCw className={cn('h-3.5 w-3.5', loading && 'animate-spin')} /> 刷新
            </Button>
            <Button
              size="sm"
              variant="ghost"
              onClick={() => {
                clearToken()
                setTok('')
              }}
            >
              <LogOut className="h-3.5 w-3.5" /> 退出
            </Button>
          </div>
        </div>
      </header>

      <div className="mx-auto max-w-7xl px-6 py-6">
        <div className="mb-5 flex gap-2">
          {tabs.map((t) => (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={cn(
                'inline-flex items-center gap-2 rounded-xl border-[3px] border-ink px-4 py-2 text-sm font-bold shadow-stickerSm btn-pop',
                tab === t.key ? 'bg-lime' : 'bg-white hover:bg-cream'
              )}
            >
              <t.icon className="h-4 w-4" /> {t.label}
            </button>
          ))}
        </div>

        {/* 概览卡片 */}
        {stats && (
          <div className="mb-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {[
              { label: '软件数', value: stats.total_software, tone: 'bg-cyan' },
              { label: '方案数', value: stats.total_plans, tone: 'bg-lime' },
              { label: '反馈数', value: stats.total_feedback, tone: 'bg-cream' },
              { label: '待处理反馈', value: stats.pending_feedback, tone: 'bg-pink text-white' },
            ].map((c) => (
              <Card key={c.label} className={cn('p-5', c.tone)}>
                <div className="font-mono text-[12.5px] text-ink/70">{c.label}</div>
                <div className="font-fun text-3xl">{c.value}</div>
              </Card>
            ))}
          </div>
        )}

        {/* 方案 */}
        {tab === 'plans' && (
          <Card>
            <div className="flex flex-wrap items-center gap-3 border-b-[3px] border-ink px-5 py-3">
              <div className="relative flex-1 min-w-[220px]">
                <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink/40" />
                <Input className="pl-9" value={q} onChange={(e) => setQ(e.target.value)} placeholder="搜软件 / 版本 / 平台" />
              </div>
              <span className="font-mono text-[12px] text-ink/50">共 {filteredPlans.length} 条</span>
            </div>
            <div className="overflow-auto">
              <table className="w-full text-[13px]">
                <thead className="bg-cream">
                  <tr>
                    {['ID', '软件', '版本', '平台', '来源', '浏览', '安装', '有效/无效', '操作'].map((h) => (
                      <th key={h} className="border-b-[3px] border-ink px-3 py-2 text-left font-bold">
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {filteredPlans.map((p) => (
                    <tr key={p.id} className="odd:bg-white even:bg-paper2/60">
                      <td className="px-3 py-2 font-mono">{p.id}</td>
                      <td className="px-3 py-2 font-bold">{p.software_name}</td>
                      <td className="px-3 py-2 font-mono">{p.version}</td>
                      <td className="px-3 py-2">
                        <Badge tone="cyan">{p.platform}</Badge>
                      </td>
                      <td className="px-3 py-2">
                        <Badge tone={p.generated_by === 'ai' ? 'lime' : p.generated_by === 'manual' ? 'dark' : 'cream'}>
                          {p.generated_by}
                        </Badge>
                      </td>
                      <td className="px-3 py-2 font-mono">{p.view_count}</td>
                      <td className="px-3 py-2 font-mono">{p.install_count}</td>
                      <td className="px-3 py-2 font-mono">
                        <span className="text-limeDark">👍{p.valid_count}</span>{' '}
                        <span className="text-pink">👎{p.invalid_count}</span>
                      </td>
                      <td className="px-3 py-2">
                        <div className="flex gap-2">
                          <Button size="sm" variant="outline" onClick={() => setEditing(p)}>
                            <PenLine className="h-3.5 w-3.5" /> 编辑
                          </Button>
                          <Button
                            size="sm"
                            variant="pink"
                            onClick={async () => {
                              if (confirm(`删掉 ${p.software_name} ${p.version} 的方案？`)) {
                                await api.deletePlan(p.id)
                                load()
                              }
                            }}
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {filteredPlans.length === 0 && (
                <div className="p-8 text-center text-ink/50">还没有方案，去桌面端生成一条吧～</div>
              )}
            </div>
          </Card>
        )}

        {/* 反馈 */}
        {tab === 'feedbacks' && (
          <Card>
            <div className="flex flex-wrap items-center gap-3 border-b-[3px] border-ink px-5 py-3">
              {[
                { k: '', label: '全部' },
                { k: 'pending', label: '待处理' },
                { k: 'resolved', label: '已处理' },
              ].map((f) => (
                <button
                  key={f.k}
                  onClick={() => setFilterStatus(f.k)}
                  className={cn(
                    'rounded-full border-2 border-ink px-3 py-1 text-[12.5px] font-bold btn-pop',
                    filterStatus === f.k ? 'bg-lime' : 'bg-white hover:bg-cream'
                  )}
                >
                  {f.label}
                </button>
              ))}
              <span className="ml-auto font-mono text-[12px] text-ink/50">共 {filteredFb.length} 条</span>
            </div>
            <div className="divide-y-2 divide-ink/15">
              {filteredFb.map((f) => (
                <div key={f.id} className="flex flex-wrap items-start gap-3 p-4">
                  <Badge tone={f.vote === 'valid' ? 'lime' : f.vote === 'invalid' ? 'pink' : 'cream'}>
                    {f.vote === 'valid' ? '👍 有效' : f.vote === 'invalid' ? '👎 无效' : '💬 留言'}
                  </Badge>
                  <div className="min-w-[200px] flex-1">
                    <div className="font-bold">
                      {f.software_name || '(未指定)'} {f.version} · {f.platform}
                    </div>
                    <div className="mt-1 whitespace-pre-wrap text-[13px] text-ink/80">
                      {f.content || '(用户没有写文字)'}
                    </div>
                    {f.reply && (
                      <div className="mt-2 rounded-lg bg-cyan/20 px-3 py-2 text-[13px]">回复：{f.reply}</div>
                    )}
                    <div className="mt-1 font-mono text-[11.5px] text-ink/45">
                      #{f.id} · 方案 {f.plan_id ?? '-'} · {f.created_at?.replace('T', ' ') ?? ''}
                    </div>
                  </div>
                  <div className="flex gap-2">
                    {f.status !== 'resolved' && (
                      <Button
                        size="sm"
                        variant="lime"
                        onClick={async () => {
                          await api.updateFeedback(f.id, { status: 'resolved' })
                          load()
                        }}
                      >
                        标记已处理
                      </Button>
                    )}
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={async () => {
                        const reply = prompt('回复内容', f.reply || '')
                        if (reply !== null) {
                          await api.updateFeedback(f.id, { reply, status: 'resolved' })
                          load()
                        }
                      }}
                    >
                      回复
                    </Button>
                  </div>
                </div>
              ))}
              {filteredFb.length === 0 && (
                <div className="p-8 text-center text-ink/50">还没有反馈～</div>
              )}
            </div>
          </Card>
        )}

        {/* 统计 */}
        {tab === 'stats' && stats && (
          <div className="grid gap-4 lg:grid-cols-2">
            <BarList title="🏆 软件被选次数" data={stats.by_software} color="bg-lime" />
            <BarList title="🏷️ 版本被选次数" data={stats.by_version} color="bg-cyan" />
            <BarList title="💻 平台分布" data={stats.by_platform} color="bg-orange" />
            <BarList title="📈 事件分布" data={stats.by_event} color="bg-pink" />
            <Card className="p-5 lg:col-span-2">
              <div className="font-fun">🔥 最受欢迎方案</div>
              <div className="mt-3 space-y-2">
                {stats.top_plans.map((p, i) => (
                  <div key={p.id} className="flex flex-wrap items-center gap-3 rounded-xl border-2 border-ink bg-white px-3 py-2">
                    <span className="font-fun text-lg">{i + 1}</span>
                    <span className="font-bold">{p.name}</span>
                    <span className="ml-auto font-mono text-[12.5px]">
                      👀{p.view} · 🚀{p.install} · 👍{p.valid} · 👎{p.invalid}
                    </span>
                  </div>
                ))}
                {stats.top_plans.length === 0 && <div className="text-ink/50">暂无数据</div>}
              </div>
            </Card>
          </div>
        )}
      </div>

      {editing && <PlanEditor plan={editing} onClose={() => setEditing(null)} onSaved={load} />}
      {showServer && <ServerDialog onClose={() => setShowServer(false)} />}
    </div>
  )
}
