export type Platform = 'windows' | 'macos' | 'linux'

export interface Software {
  id: number
  name: string
  slug: string
  icon: string
  tagline: string
  category: string
  official_url: string
  install_type: string
  source_kind: string
}

export interface Plan {
  id: number
  software_id: number
  software_name: string
  version: string
  platform: string
  title: string
  summary: string
  content_md: string
  official_url: string
  generated_by: string
  view_count: number
  install_count: number
  valid_count: number
  invalid_count: number
}

const KEY = 'zlm:api-base'

// 打包版默认连线上后端；本地开发由 .env.development 覆盖为 127.0.0.1:8899。
// 用户在设置里手动填过的地址优先级最高（存 localStorage）。
const DEFAULT_BASE =
  (import.meta.env.VITE_API_BASE as string | undefined)?.replace(/\/$/, '') ||
  'http://127.0.0.1:8899'

export function getApiBase() {
  return localStorage.getItem(KEY) || DEFAULT_BASE
}

export function setApiBase(v: string) {
  localStorage.setItem(KEY, v.replace(/\/$/, ''))
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${getApiBase()}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(`${res.status} ${text.slice(0, 200)}`)
  }
  return res.json() as Promise<T>
}

export const api = {
  health: () => req<{ ok: boolean; ai_enabled: boolean }>('/api/health'),
  softwares: (q = '') =>
    req<{ items: Software[] }>(`/api/softwares?q=${encodeURIComponent(q)}&limit=60`),
  resolve: (query: string) =>
    req<{ software: Software }>('/api/resolve', {
      method: 'POST',
      body: JSON.stringify({ query }),
    }),
  // platform=windows 时服务端会以 winget 真实可装版本为准
  versions: (key: string, refresh = false, platform = '') =>
    req<{ latest: string | null; source: string; versions: { version: string; is_latest: number }[] }>(
      `/api/softwares/${encodeURIComponent(key)}/versions?refresh=${refresh}&platform=${encodeURIComponent(platform)}`
    ),
  generate: (software: string, version: string, platform: string, force = false, fast = false) =>
    req<{ plan: Plan }>('/api/plans/generate', {
      method: 'POST',
      body: JSON.stringify({ software, version, platform, force, fast }),
    }),
  plan: (id: number) => req<{ plan: Plan }>(`/api/plans/${id}`),
  install: (id: number) => req<{ ok: boolean }>(`/api/plans/${id}/install`, { method: 'POST' }),
  vote: (id: number, vote: string, content = '') =>
    req<{ ok: boolean }>(`/api/plans/${id}/vote`, {
      method: 'POST',
      body: JSON.stringify({ vote, content }),
    }),
  event: (payload: Record<string, string>) =>
    req<{ ok: boolean }>('/api/events', { method: 'POST', body: JSON.stringify(payload) }),
}

type Block = { lang: string; code: string }

function parseBlocks(md: string): Block[] {
  // 容忍 ```powershell\r\n 这种 CRLF 结尾
  const re = /```(\w+)?[ \t]*\r?\n([\s\S]*?)```/g
  const blocks: Block[] = []
  let m: RegExpExecArray | null
  while ((m = re.exec(md))) {
    blocks.push({ lang: (m[1] || '').toLowerCase(), code: m[2] })
  }
  return blocks
}

/** 取某个标题下的正文（到同级或更高级标题为止） */
function sectionOf(md: string, keyword: string): string | null {
  const lines = md.split(/\r?\n/)
  let start = -1
  let level = 0
  for (let i = 0; i < lines.length; i++) {
    const m = /^(#{1,6})\s+(.*)$/.exec(lines[i].trim())
    if (m && m[2].includes(keyword)) {
      start = i + 1
      level = m[1].length
      break
    }
  }
  if (start < 0) return null
  const buf: string[] = []
  for (let i = start; i < lines.length; i++) {
    const m = /^(#{1,6})\s+/.exec(lines[i].trim())
    if (m && m[1].length <= level) break
    buf.push(lines[i])
  }
  return buf.join('\n')
}

const WIN_LANGS = ['powershell', 'ps1', 'pwsh', 'bat', 'cmd']
const NIX_LANGS = ['bash', 'sh', 'shell', 'zsh', 'console']

/**
 * 从方案里挑出「该真正执行的」脚本：
 * 1) 优先「一键安装脚本」小节里的脚本块
 * 2) 其次平台匹配的脚本块里最长的那个（避免抓到「快速命令」这类短片段）
 * 3) 再退到任意脚本块里最长的
 */
export function extractScript(md: string, platform: Platform): { code: string; lang: string } | null {
  const wanted = platform === 'windows' ? WIN_LANGS : NIX_LANGS
  const fallbackLangs = [...WIN_LANGS, ...NIX_LANGS]
  const longest = (list: Block[]) =>
    list.length ? list.reduce((a, b) => (b.code.length > a.code.length ? b : a)) : null

  // 1. 「一键安装脚本」小节
  const sec = sectionOf(md, '一键安装脚本')
  if (sec) {
    const blocks = parseBlocks(sec)
    const hit =
      longest(blocks.filter((b) => wanted.includes(b.lang))) ||
      longest(blocks.filter((b) => fallbackLangs.includes(b.lang)))
    if (hit) return { code: hit.code, lang: hit.lang }
  }

  const all = parseBlocks(md)
  // 2. 平台匹配的最长块
  const byPlatform = longest(all.filter((b) => wanted.includes(b.lang)))
  if (byPlatform) return { code: byPlatform.code, lang: byPlatform.lang }
  // 3. 任意脚本语言的最长块
  const anyScript = longest(all.filter((b) => fallbackLangs.includes(b.lang)))
  if (anyScript) return { code: anyScript.code, lang: anyScript.lang }
  return null
}
