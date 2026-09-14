import { useEffect, useState } from 'react'
import { api } from '../api'
import Markdown from '../components/Markdown'

export default function Knowledge() {
  const [q, setQ] = useState('profile')
  const [chunks, setChunks] = useState<string[]>([])
  const [loading, setLoading] = useState(false)

  const search = async () => {
    if (!q.trim()) return
    setLoading(true)
    try {
      const r = await api.knowledge(q)
      setChunks(r.chunks)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { search() }, [])

  return (
    <div>
      <h2 className="text-lg font-semibold mb-4">Knowledge (Local RAG)</h2>
      <form onSubmit={(e) => { e.preventDefault(); search() }} className="flex gap-2 mb-5">
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search project knowledge…"
          className="flex-1 px-3 py-2 rounded bg-neutral-950 border border-neutral-700 text-neutral-200 focus:outline-none focus:border-neutral-500"
        />
        <button
          type="submit"
          disabled={loading}
          className="px-4 py-2 rounded bg-neutral-800 hover:bg-neutral-700 text-neutral-100 disabled:opacity-60"
        >
          {loading ? 'Searching…' : 'Search'}
        </button>
      </form>
      {chunks.length === 0 ? (
        <div className="text-sm text-neutral-500 border border-dashed border-neutral-800 rounded-lg p-8 text-center">
          No results. Ingest documents first: <code className="text-neutral-300">python -m openharness ingest .openharness</code>
        </div>
      ) : (
        <div className="space-y-4">
          {chunks.map((c, i) => (
            <div key={i} className="border border-neutral-800 rounded-lg p-4 bg-neutral-900/40">
              <div className="text-xs text-neutral-500 mb-2">Chunk {i + 1} · {c.length} chars</div>
              <Markdown text={c} />
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
