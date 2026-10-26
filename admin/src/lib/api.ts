export interface Plan {
  id: number
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
  updated_at?: string
}

export interface Feedback {
  id: number
  plan_id: number | null
  software_name: string
  version: string
  platform: string
  vote: string
  content: string
  status: string
  reply: string
  created_at?: string
}

export interface Stats {
  total_plans: number
  total_software: number
  total_feedback: number
  pending_feedback: number
  by_software: { name: string; count: number }[]
  by_version: { name: string; count: number }[]
  by_platform: { name: string; count: number }[]
  by_event: { name: string; count: number }[]
  top_plans: { id: number; name: string; view: number; install: number; valid: number; invalid: number }[]
}

const TOKEN_KEY = 'zlm:admin-token'
export const getToken = () => localStorage.getItem(TOKEN_KEY) || ''
export const setToken = (t: string) => localStorage.setItem(TOKEN_KEY, t)
export const clearToken = () => localStorage.removeItem(TOKEN_KEY)

const BASE = import.meta.env.DEV ? '' : (localStorage.getItem('zlm:admin-base') || 'http://127.0.0.1:8899')

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      'X-Admin-Token': getToken(),
    },
    ...init,
  })
  if (res.status === 401) {
    clearToken()
    throw new Error('登录已失效，请重新登录')
  }
  if (!res.ok) throw new Error(`${res.status} ${(await res.text()).slice(0, 200)}`)
  return res.json() as Promise<T>
}

export const api = {
  login: (password: string) =>
    req<{ ok: boolean; token: string }>('/api/admin/login', {
      method: 'POST',
      body: JSON.stringify({ username: 'admin', password }),
    }),
  health: () => req<{ ok: boolean; ai_enabled: boolean; model: string }>('/api/health'),
  plans: (q = '') => req<{ items: Plan[] }>(`/api/plans?q=${encodeURIComponent(q)}&limit=200`),
  updatePlan: (id: number, data: Partial<Plan>) =>
    req<{ plan: Plan }>(`/api/admin/plans/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    }),
  deletePlan: (id: number) => req<{ ok: boolean }>(`/api/admin/plans/${id}`, { method: 'DELETE' }),
  regenerate: (id: number) =>
    req<{ plan: Plan }>(`/api/admin/plans/${id}/regenerate`, { method: 'POST' }),
  feedbacks: (status = '') =>
    req<{ items: Feedback[] }>(`/api/admin/feedbacks?status=${status}&limit=300`),
  updateFeedback: (id: number, data: Partial<Feedback>) =>
    req<{ feedback: Feedback }>(`/api/admin/feedbacks/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    }),
  stats: () => req<Stats>('/api/stats/overview'),
}
