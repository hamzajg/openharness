import { useEffect, useState } from 'react'
import { api, SessionMeta } from '../api'

function useInterval(cb: () => void, ms: number) {
  useEffect(() => {
    const id = setInterval(cb, ms)
    return () => clearInterval(id)
  }, [cb, ms])
}

function fmtAgo(ts: number) {
  const s = Math.max(1, Math.floor((Date.now() - ts * 1000) / 1000))
  if (s < 60) return `${s}s ago`
  if (s < 3600) return `${Math.floor(s / 60)}m ago`
  return `${Math.floor(s / 3600)}h ago`
}

function TranscriptView({ id }: { id: string }) {
  const [lines, setLines] = useState<unknown[]>([])
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    let es: EventSource | null = null
    ;(async () => {
      try {
        const initial = await api.sessionLines(id)
        if (!cancelled) setLines(initial.lines)
      } catch (e: any) {
        setError(e?.message || 'Failed to load transcript')
        return
      }
      try {
        es = new EventSource(`/api/stream/${encodeURIComponent(id)}`)
        es.addEventListener('line', (ev: MessageEvent) => {
          try {
            const data = JSON.parse(ev.data)
            setLines((prev) => [...prev, data])
          } catch {}
        })
        es.onerror = () => setError('Stream error — reloading may help')
      } catch (e: any) {
        setError(e?.message || 'Stream failed')
      }
    })()
    return () => {
      cancelled = true
      if (es) es.close()
    }
  }, [id])

  return (
    <div className="mt-3 border border-neutral-800 rounded-lg overflow-hidden">
      <div className="px-3 py-2 bg-neutral-900 border-b border-neutral-800 text-xs text-neutral-400 flex justify-between">
        <span>Transcript · {id}</span>
        <span>{lines.length} lines</span>
      </div>
      {error ? (
        <div className="p-3 text-sm text-red-400">{error}</div>
      ) : (
        <div className="max-h-[60vh] overflow-y-auto p-3 font-mono text-xs space-y-1 text-neutral-300">
          {lines.map((l, i) => (
            <div key={i} className="whitespace-pre-wrap break-all">
              {typeof l === 'string' ? l : JSON.stringify(l, null, 0)}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export default function Sessions() {
  const [data, setData] = useState<Record<string, SessionMeta[]>>({})
  const [activeId, setActiveId] = useState<string | null>(null)
  const [err, setErr] = useState<string | null>(null)

  const load = async () => {
    try {
      const d = await api.sessions()
      setData(d)
    } catch (e: any) {
      setErr(e?.message || 'Failed to load sessions')
    }
  }

  useEffect(() => { load() }, [])
  useInterval(load, 5000)

  const repos = Object.keys(data)
  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold">Agent Sessions</h2>
        <span className="text-xs text-neutral-500">auto-refresh 5s</span>
      </div>
      {err && <div className="mb-3 text-sm text-red-400">{err}</div>}
      {repos.length === 0 ? (
        <div className="text-sm text-neutral-500 border border-dashed border-neutral-800 rounded-lg p-8 text-center">
          No agent sessions observed yet. Run <code className="text-neutral-300">oh serve</code> in one terminal and launch <code className="text-neutral-300">opencode</code> / <code className="text-neutral-300">claude</code> in another.
        </div>
      ) : (
        <div className="space-y-6">
          {repos.map((repo) => (
            <section key={repo}>
              <h3 className="text-sm font-medium text-neutral-300 mb-2 flex items-center gap-2">
                <span className="inline-block w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
                {repo === 'external' ? 'External sessions' : `sources/${repo}`}
                <span className="text-neutral-500 text-xs font-normal">({data[repo].length})</span>
              </h3>
              <div className="border border-neutral-800 rounded-lg overflow-hidden">
                <table className="w-full text-sm">
                  <thead className="bg-neutral-900/50 text-neutral-400 text-xs">
                    <tr>
                      <th className="text-left px-3 py-2 font-normal">Agent</th>
                      <th className="text-left px-3 py-2 font-normal">Project</th>
                      <th className="text-left px-3 py-2 font-normal">Last seen</th>
                      <th className="text-left px-3 py-2 font-normal">Current command</th>
                      <th className="px-3 py-2"></th>
                    </tr>
                  </thead>
                  <tbody>
                    {data[repo].map((s) => (
                      <tr key={s.id} className="border-t border-neutral-800/70 hover:bg-neutral-900/40">
                        <td className="px-3 py-2">
                          <span className="inline-flex items-center gap-1.5">
                            <span className={`inline-block w-2 h-2 rounded-full ${s.active ? 'bg-emerald-500' : 'bg-neutral-600'}`}></span>
                            <span className="text-neutral-200">{s.agent}</span>
                          </span>
                        </td>
                        <td className="px-3 py-2 text-neutral-300 truncate max-w-xs" title={s.project_path}>{s.project_path}</td>
                        <td className="px-3 py-2 text-neutral-400">{fmtAgo(s.last_seen)}</td>
                        <td className="px-3 py-2 text-neutral-400 truncate max-w-xs">{s.current_command || '—'}</td>
                        <td className="px-3 py-2 text-right">
                          <button
                            onClick={() => setActiveId(activeId === s.id ? null : s.id)}
                            className="text-xs px-2 py-1 rounded bg-neutral-800 hover:bg-neutral-700 text-neutral-200"
                          >
                            {activeId === s.id ? 'Hide' : 'View'}
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {activeId && data[repo].some(s => s.id === activeId) && <TranscriptView id={activeId} />}
            </section>
          ))}
        </div>
      )}
    </div>
  )
}
