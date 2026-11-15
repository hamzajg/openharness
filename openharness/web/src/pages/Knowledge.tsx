import { useEffect, useState } from 'react'
import { api } from '../api'
import Markdown from '../components/Markdown'

export default function Knowledge() {
  const [q, setQ] = useState('profile')
  const [chunks, setChunks] = useState<string[]>([])
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  const search = async () => {
    if (!q.trim()) return
    setLoading(true)
    setErr(null)
    try {
      const r = await api.knowledge(q)
      setChunks(r.chunks)
    } catch (e: any) {
      setErr(e?.message || 'Search failed')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { search() }, [])

  return (
    <div className="space-y-6 max-w-5xl">
      <div>
        <h2 className="text-xl font-semibold text-neutral-100">Knowledge</h2>
        <p className="text-sm text-neutral-500 mt-1">
          Local RAG over ingested docs — semantic search, fully on-device.
        </p>
      </div>

      <form onSubmit={(e) => { e.preventDefault(); search() }} className="flex gap-2">
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search project knowledge…"
          className="flex-1 px-3 py-2 rounded-lg bg-neutral-950 border border-neutral-800 text-sm text-neutral-200 placeholder:text-neutral-600 focus:outline-none focus:border-sky-500"
        />
        <button
          type="submit"
          disabled={loading}
          className="px-4 py-2 rounded-lg bg-sky-600 hover:bg-sky-500 text-white text-sm font-medium disabled:opacity-60 disabled:cursor-not-allowed transition-colors"
        >
          {loading ? 'Searching…' : 'Search'}
        </button>
      </form>

      {err && <div className="text-sm text-red-400">{err}</div>}

      {chunks.length === 0 && !loading ? (
        <div className="rounded-xl border border-dashed border-neutral-800 p-12 text-center">
          <p className="text-sm text-neutral-500">No results.</p>
          <p className="text-xs text-neutral-600 mt-1.5 font-mono">
            ingest docs first: python -m openharness ingest .openharness
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          <p className="text-xs text-neutral-500">
            {chunks.length} result{chunks.length === 1 ? '' : 's'}
            {q ? <> for <span className="text-neutral-300 font-mono">"{q}"</span></> : null}
          </p>
          {chunks.map((c, i) => (
            <div key={i} className="rounded-xl border border-neutral-800 bg-neutral-900/60 overflow-hidden">
              <div className="px-4 py-2 border-b border-neutral-800/70 flex items-center gap-2">
                <span className="text-[11px] font-semibold text-neutral-500">#{i + 1}</span>
                <span className="text-[11px] text-neutral-600 font-mono">{c.length} chars</span>
              </div>
              <div className="p-4">
                <Markdown text={c} />
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
