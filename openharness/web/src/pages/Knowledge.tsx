import { useEffect, useState } from 'react'
import { api } from '../api'
import Markdown from '../components/Markdown'
import {
  Button,
  Card,
  EmptyState,
  ErrorNote,
  Input,
  Loading,
  Toolbar,
} from '../components/ui'

export default function Knowledge() {
  const [q, setQ] = useState('profile')
  const [chunks, setChunks] = useState<string[]>([])
  const [searched, setSearched] = useState(false)
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const [lastQuery, setLastQuery] = useState('')

  const search = async (query: string) => {
    const trimmed = query.trim()
    if (!trimmed) return
    setLoading(true)
    setErr(null)
    try {
      const r = await api.knowledge(trimmed)
      setChunks(r.chunks)
      setLastQuery(trimmed)
    } catch (e: any) {
      setErr(e?.message || 'Search failed')
      setChunks([])
    } finally {
      setLoading(false)
      setSearched(true)
    }
  }

  useEffect(() => {
    search('profile')
  }, [])

  return (
    <div className="space-y-6">
      <Toolbar>
        <form
          onSubmit={(e) => {
            e.preventDefault()
            search(q)
          }}
          className="flex w-full gap-2"
        >
          <Input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search project knowledge…"
            aria-label="Search query"
          />
          <Button type="submit" variant="primary" disabled={loading}>
            {loading ? 'Searching…' : 'Search'}
          </Button>
        </form>
      </Toolbar>

      {err && <ErrorNote>{err}</ErrorNote>}

      {loading ? (
        <Loading label="Searching…" />
      ) : chunks.length === 0 ? (
        searched && (
          <EmptyState
            title={`No results for “${lastQuery}”.`}
            hint="ingest docs first: python -m openharness ingest .openharness"
          />
        )
      ) : (
        <div className="space-y-3">
          <p className="text-xs text-ink-mute">
            {chunks.length} result{chunks.length === 1 ? '' : 's'} for{' '}
            <span className="font-mono text-ink-body">“{lastQuery}”</span>
          </p>
          {chunks.map((chunk, i) => (
            <Card key={i}>
              <div className="flex items-center gap-2 border-b border-line/70 px-4 py-2">
                <span className="text-[11px] font-semibold text-ink-mute">#{i + 1}</span>
                <span className="font-mono text-[11px] text-ink-faint">
                  {chunk.length} chars
                </span>
              </div>
              <div className="p-4">
                <Markdown text={chunk} />
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}
