const BASE = '/api'

async function _fetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(BASE + path, init)
  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(`HTTP ${res.status}: ${text || res.statusText}`)
  }
  if (res.headers.get('content-type')?.includes('application/json')) {
    return (await res.json()) as T
  }
  return (await res.text()) as unknown as T
}

export interface Skill {
  name: string
  description: string
  params: Record<string, string>
  non_deterministic: boolean
}

export interface SessionMeta {
  id: string
  agent: string
  project_path: string
  last_seen: number
  current_command: string
  file: string
  active: boolean
}

export const api = {
  sessions: () => _fetch<Record<string, SessionMeta[]>>('/sessions'),
  sessionLines: (id: string) => _fetch<{ lines: unknown[] }>(`/sessions/${encodeURIComponent(id)}`),
  skills: () => _fetch<Skill[]>('/skills'),
  runSkill: (name: string, params: Record<string, unknown>) =>
    _fetch<{ ok: boolean; result?: string; error?: string }>(
      `/skills/${encodeURIComponent(name)}/run`,
      { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(params) },
    ),
  self: (block?: string) =>
    _fetch<{ text: string; block: string }>(block ? `/self?block=${encodeURIComponent(block)}` : '/self'),
  env: () => _fetch<{ probe: unknown; env_declared: unknown; env_content: string; drift: string }>('/env'),
  knowledge: (q: string, k = 5) =>
    _fetch<{ query: string; chunks: string[] }>(`/knowledge?q=${encodeURIComponent(q)}&k=${k}`),
}
