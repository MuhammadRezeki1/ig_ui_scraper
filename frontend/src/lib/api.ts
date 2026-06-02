import type { ApiResponse, SessionInfo, AuthStatus, PostResult, Profile, OutputFile, HealthData } from '@/types'

const BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

async function apiFetch<T>(path: string, init?: RequestInit): Promise<ApiResponse<T>> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...init?.headers },
    ...init,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ message: res.statusText }))
    throw new Error(err.message || `HTTP ${res.status}`)
  }
  return res.json()
}

// ── Health ──────────────────────────────────────────────────────
export const getHealth = () => apiFetch<HealthData>('/api/health')

// ── Auth ────────────────────────────────────────────────────────
export const getSession      = () => apiFetch<SessionInfo>('/api/auth/session')
export const getAuthStatus   = () => apiFetch<AuthStatus>('/api/auth/status')
export const triggerLogin    = () => apiFetch('/api/auth/login', { method: 'POST', body: '{}' })
export const triggerLogout   = () => apiFetch('/api/auth/logout', { method: 'POST', body: '{}' })
export const saveCookies     = (cookies_json: string) =>
  apiFetch('/api/auth/cookies', { method: 'POST', body: JSON.stringify({ cookies_json }) })

// ── Scrape ──────────────────────────────────────────────────────
export const scrapePost = (url: string, max_comments = 100) =>
  apiFetch<PostResult>('/api/scrape/post', {
    method: 'POST',
    body: JSON.stringify({ url, max_comments }),
  })

export const scrapePosts = (urls: string[], max_comments = 100, delay_between = 8) =>
  apiFetch('/api/scrape/posts/batch', {
    method: 'POST',
    body: JSON.stringify({ urls, max_comments, delay_between }),
  })

export const scrapeProfile = (username: string, save_snapshot = true) =>
  apiFetch<{ profile: Profile }>('/api/scrape/profile', {
    method: 'POST',
    body: JSON.stringify({ username, save_snapshot }),
  })

// ── Analytics ───────────────────────────────────────────────────
export const listProfiles   = () => apiFetch<{ users: Profile[]; count: number }>('/api/profiles')
export const getProfile     = (username: string) => apiFetch<{ profile: Profile }>(`/api/profiles/${username}`)
export const profileHistory = (username: string, limit = 30) =>
  apiFetch(`/api/profiles/${username}/history?limit=${limit}`)
export const profileGrowth  = (username: string) => apiFetch(`/api/profiles/${username}/growth`)
export const profileMonthly = (username: string) => apiFetch(`/api/profiles/${username}/monthly`)

// ── Output files ─────────────────────────────────────────────────
export const listOutputFiles = () => apiFetch<{ files: OutputFile[]; count: number }>('/api/output/list')
export const getOutputFile   = (filename: string) => fetch(`${BASE}/api/output/${filename}`).then(r => r.json())