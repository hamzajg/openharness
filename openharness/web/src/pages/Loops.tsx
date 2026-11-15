import { useEffect, useMemo, useRef, useState } from 'react'
import { api, LoopDetail, LoopSummary } from '../api'

const STATUS_ORDER: Record<string, number> = { running: 0, blocked: 1, done: 2 }

function statusRank(s: LoopSummary) {
  return STATUS_ORDER[s.status] ?? 3
}

function fmtAgo(iso: string) {
  const t = Date.parse(iso)
  if (!t) return '—'
  const s = Math.max(0, Math.floor((Date.now() - t) / 1000))
  if (s < 60) return `${s}s ago`
  if (s < 3600) return `${Math.floor(s / 60)}m ago`
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`
  return `${Math.floor(s / 86400)}d ago`
}

function fmtTime(iso: string) {
  const t = Date.parse(iso)
  if (!t) return iso || '—'
  return new Date(t).toLocaleString(undefined, {
    month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
  })
}

const STATUS_STYLE: Record<string, { pill: string; dot: string; bar: string }> = {
  running: {
    pill: 'bg-sky-500/15 text-sky-300 ring-sky-500/30',
    dot: 'bg-sky-400 animate-pulse',
    bar: 'from-sky-500 to-cyan-400',
  },
  blocked: {
    pill: 'bg-amber-500/15 text-amber-300 ring-amber-500/30',
    dot: 'bg-amber-400',
    bar: 'from-amber-500 to-orange-400',
  },
  done: {
    pill: 'bg-emerald-500/15 text-emerald-300 ring-emerald-500/30',
    dot: 'bg-emerald-400',
    bar: 'from-emerald-500 to-teal-400',
  },
}

function style(status: string) {
  return STATUS_STYLE[status] ?? {
    pill: 'bg-neutral-500/15 text-neutral-300 ring-neutral-500/30',
    dot: 'bg-neutral-400',
    bar: 'from-neutral-500 to-neutral-400',
  }
}

function WaveChip({ status }: { status: string }) {
  const map: Record<string, string> = {
    done: 'bg-emerald-500/20 text-emerald-300 ring-emerald-500/40',
    'in-progress': 'bg-sky-500/20 text-sky-300 ring-sky-500/40 animate-pulse',
    pending: 'bg-neutral-700/40 text-neutral-500 ring-neutral-700',
  }
  return (
    <span className={`px-1.5 py-0.5 rounded text-[10px] font-mono ring-1 ${map[status] ?? map.pending}`}>
      {status === 'in-progress' ? '▸' : status === 'done' ? '✓' : '·'}
    </span>
  )
}

function LoopCard({
  loop, detail, open, onToggle,
}: {
  loop: LoopSummary
  detail: LoopDetail | null
  open: boolean
  onToggle: () => void
}) {
  const st = style(loop.status)
  const waveEntries = detail ? Object.entries(detail.waves).sort((a, b) => Number(a[0]) - Number(b[0])) : []
  const waveStatuses = waveEntries.map(([, w]) => w.status)
  const gateEntries = detail ? Object.entries(detail.gates).sort() : []
  const pct = loop.waves_total ? Math.round((loop.waves_done / loop.waves_total) * 100) : 0

  return (
    <div className="rounded-xl border border-neutral-800 bg-neutral-900/60 overflow-hidden">
      <button onClick={onToggle} className="w-full text-left p-4 hover:bg-neutral-800/30 transition-colors">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <span className={`w-2 h-2 rounded-full ${st.dot}`} />
              <span className="text-sm font-medium text-neutral-100 truncate">
                {loop.repo} <span className="text-neutral-500 font-normal">/</span>{' '}
                <span className="font-mono text-neutral-300">{loop.feature}</span>
              </span>
            </div>
            <div className="mt-1.5 flex items-center gap-2 text-[11px] text-neutral-500">
              <span className="font-mono">{loop.iterations} iter</span>
              <span>·</span>
              <span>waves {loop.waves_done}/{loop.waves_total}</span>
              {loop.gates_total > 0 && (
                <>
                  <span>·</span>
                  <span className={loop.gates_pending > 0 ? 'text-amber-400/80' : ''}>
                    {loop.gates_total - loop.gates_pending}/{loop.gates_total} gates
                  </span>
                </>
              )}
              <span>·</span>
              <span>{fmtAgo(loop.updated)}</span>
            </div>
          </div>
          <span className={`shrink-0 px-2 py-0.5 rounded-full text-[11px] font-medium ring-1 ${st.pill}`}>
            {loop.status}
          </span>
        </div>

        <div className="mt-3 h-1.5 rounded-full bg-neutral-800 overflow-hidden">
          <div
            className={`h-full rounded-full bg-gradient-to-r ${st.bar} transition-all duration-700`}
            style={{ width: `${loop.status === 'done' ? 100 : pct}%` }}
          />
        </div>

        {waveStatuses.length > 0 && (
          <div className="mt-2.5 flex items-center gap-1">
            {waveStatuses.map((s, i) => <WaveChip key={i} status={s} />)}
          </div>
        )}

        {loop.last_event && (
          <p className="mt-2 text-[11px] text-neutral-500 truncate font-mono">
            {loop.last_event.replace(/^\d{4}-\d{2}-\d{2}T[\d:]+Z\s*/, '')}
          </p>
        )}
      </button>

      {open && (
        <div className="border-t border-neutral-800 p-4 space-y-5 bg-neutral-950/40">
          {!detail && <p className="text-xs text-neutral-500">Loading…</p>}

          {detail && waveEntries.length > 0 && (
            <section>
              <h3 className="text-[11px] font-semibold uppercase tracking-wider text-neutral-500 mb-2">Waves</h3>
              <div className="space-y-1.5">
                {waveEntries.map(([n, w]) => (
                  <div key={n} className="flex items-start gap-3 text-xs">
                    <span className="font-mono text-neutral-500 w-4 shrink-0">w{n}</span>
                    <WaveChip status={w.status} />
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2 text-neutral-300">
                        <span className="font-mono text-neutral-400">{w.branch}</span>
                        {w.pr !== '—' && <span className="text-neutral-500">PR {w.pr}</span>}
                        <span className="text-neutral-600 ml-auto shrink-0">{fmtTime(w.updated)}</span>
                      </div>
                      {w.evidence !== '—' && (
                        <p className="mt-0.5 text-neutral-500 truncate" title={w.evidence}>{w.evidence}</p>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </section>
          )}

          {detail && gateEntries.length > 0 && (
            <section>
              <h3 className="text-[11px] font-semibold uppercase tracking-wider text-neutral-500 mb-2">Gates</h3>
              <div className="space-y-1.5">
                {gateEntries.map(([gid, g]) => (
                  <div key={gid} className="flex items-start gap-3 text-xs">
                    <span className="font-mono text-neutral-400 w-8 shrink-0">{gid}</span>
                    <span className={`px-1.5 py-0.5 rounded text-[10px] font-mono ring-1 shrink-0 ${
                      g.status === 'met' ? 'bg-emerald-500/20 text-emerald-300 ring-emerald-500/40'
                      : g.status === 'waived' ? 'bg-violet-500/20 text-violet-300 ring-violet-500/40'
                      : g.status === 'failed' ? 'bg-red-500/20 text-red-300 ring-red-500/40'
                      : 'bg-neutral-700/40 text-neutral-400 ring-neutral-700'
                    }`}>{g.status}</span>
                    <p className="min-w-0 flex-1 text-neutral-500 truncate" title={g.evidence}>
                      {g.evidence !== '—' ? g.evidence : ''}
                    </p>
                  </div>
                ))}
              </div>
            </section>
          )}

          {detail && detail.events.length > 0 && (
            <section>
              <h3 className="text-[11px] font-semibold uppercase tracking-wider text-neutral-500 mb-2">
                Events <span className="text-neutral-600">({detail.events.length})</span>
              </h3>
              <ol className="relative border-l border-neutral-800 ml-1.5 space-y-2">
                {[...detail.events].reverse().map((e, i) => {
                  const m = e.match(/^(\S+)\s+(.*)$/)
                  return (
                    <li key={i} className="relative pl-4">
                      <span className={`absolute -left-[3.5px] top-1 w-1.5 h-1.5 rounded-full ${
                        i === 0 ? 'bg-sky-400' : 'bg-neutral-700'
                      }`} />
                      <span className="text-neutral-600 font-mono text-[10px]">{m?.[1] ?? ''}</span>{' '}
                      <span className="text-neutral-400 text-[11px]">{m?.[2] ?? e}</span>
                    </li>
                  )
                })}
              </ol>
            </section>
          )}
        </div>
      )}
    </div>
  )
}

export default function Loops() {
  const [loops, setLoops] = useState<LoopSummary[]>([])
  const [live, setLive] = useState(false)
  const [openKey, setOpenKey] = useState<string | null>(null)
  const [details, setDetails] = useState<Record<string, LoopDetail>>({})
  const detailsRef = useRef(details)
  detailsRef.current = details

  useEffect(() => {
    let cancelled = false
    api.loops().then((r) => { if (!cancelled) setLoops(r.loops) }).catch(() => {})

    const es = new EventSource('/api/loops/stream')
    es.addEventListener('open', () => setLive(true))
    es.addEventListener('loops', (ev: MessageEvent) => {
      try {
        const next: LoopSummary[] = JSON.parse(ev.data)
        setLoops(next)
        // refresh expanded details that may have changed
        const open = Object.keys(detailsRef.current)
        for (const key of open) {
          const slash = key.indexOf('/')
          const repo = key.slice(0, slash)
          const feature = key.slice(slash + 1)
          if (next.some((l) => l.repo === repo && l.feature === feature)) {
            api.loopDetail(repo, feature)
              .then((d) => setDetails((p) => ({ ...p, [key]: d })))
              .catch(() => {})
          }
        }
      } catch {}
    })
    es.onerror = () => setLive(false)
    return () => { cancelled = true; es.close() }
  }, [])

  const sorted = useMemo(
    () => [...loops].sort((a, b) => statusRank(a) - statusRank(b) || b.updated.localeCompare(a.updated)),
    [loops],
  )
  const counts = useMemo(() => ({
    running: loops.filter((l) => l.status === 'running').length,
    blocked: loops.filter((l) => l.status === 'blocked').length,
    done: loops.filter((l) => l.status === 'done').length,
  }), [loops])

  const toggle = (l: LoopSummary) => {
    const key = `${l.repo}/${l.feature}`
    setOpenKey((cur) => (cur === key ? null : key))
    if (!details[key]) {
      api.loopDetail(l.repo, l.feature)
        .then((d) => setDetails((p) => ({ ...p, [key]: d })))
        .catch(() => {})
    }
  }

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-neutral-100">Delivery Loops</h2>
          <p className="text-xs text-neutral-500 mt-0.5">
            ship_loop state across <span className="font-mono">sources/*/specs/*/</span> — live via SSE
          </p>
        </div>
        <div className="flex items-center gap-3 text-xs">
          <span className="flex items-center gap-1.5 text-neutral-400">
            <span className={`w-1.5 h-1.5 rounded-full ${live ? 'bg-emerald-400 animate-pulse' : 'bg-neutral-600'}`} />
            {live ? 'LIVE' : 'reconnecting…'}
          </span>
          <span className="text-neutral-600">|</span>
          <span className="text-sky-300">{counts.running} running</span>
          <span className="text-amber-300">{counts.blocked} blocked</span>
          <span className="text-emerald-300">{counts.done} done</span>
        </div>
      </div>

      {sorted.length === 0 && (
        <div className="rounded-xl border border-dashed border-neutral-800 p-10 text-center">
          <p className="text-sm text-neutral-500">No delivery loops found.</p>
          <p className="text-xs text-neutral-600 mt-1 font-mono">
            loops appear here once a feature has specs/&lt;feature&gt;/LOOP.state.json
          </p>
        </div>
      )}

      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {sorted.map((l) => {
          const key = `${l.repo}/${l.feature}`
          return (
            <LoopCard
              key={key}
              loop={l}
              detail={details[key] ?? null}
              open={openKey === key}
              onToggle={() => toggle(l)}
            />
          )
        })}
      </div>
    </div>
  )
}
