import { useEffect, useMemo, useRef, useState } from 'react'
import { api, LoopDetail, LoopSummary } from '../api'

type Filter = 'all' | 'attention' | 'running' | 'done'

const FILTERS: { key: Filter; label: string }[] = [
  { key: 'all', label: 'All' },
  { key: 'attention', label: 'Needs you' },
  { key: 'running', label: 'In progress' },
  { key: 'done', label: 'Done' },
]

/* ---------- formatting helpers ---------- */

function fmtAgo(iso: string) {
  const t = Date.parse(iso)
  if (!t) return '—'
  const s = Math.max(0, Math.floor((Date.now() - t) / 1000))
  if (s < 60) return `${s}s ago`
  if (s < 3600) return `${Math.floor(s / 60)}m ago`
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`
  return `${Math.floor(s / 86400)}d ago`
}

function fmtDateTime(iso: string) {
  const t = Date.parse(iso)
  if (!t || iso === '—') return '—'
  return new Date(t).toLocaleString(undefined, {
    month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
  })
}

/** "2026-…Z complete wave 2 (#8): evidence…" → {time, text} humanized. */
function humanizeEvent(raw: string) {
  const m = raw.match(/^(\S+)\s+(.*)$/)
  const ts = m?.[1] ?? ''
  let text = m?.[2] ?? raw
  const sub = (re: RegExp, fn: (...a: string[]) => string) => {
    const mm = text.match(re)
    if (mm) text = fn(...mm.slice(1))
  }
  sub(/start wave (\d+) on (\S+)/, (w, b) => `Started wave ${w} on ${b}`)
  sub(/complete wave (\d+) \((#\d+)\):?\s*(.*)/, (w, pr, ev) =>
    `Completed wave ${w} (${pr})${ev ? ` — ${ev}` : ''}`)
  sub(/^blocked:\s*(G\d+):\s*(.*)/, (g, why) => `Blocked — ${g}: ${why}`)
  sub(/^blocked:\s*(.*)/, (why) => `Blocked — ${why}`)
  sub(/^feature validated and shipped/, () => 'Feature validated and shipped')
  sub(/^feature done/, () => 'Feature done')
  return { ts, text }
}

/** Pull the blocking reason out of the last event for the attention banner. */
function blockReason(loop: LoopSummary): string | null {
  if (loop.status !== 'blocked' || !loop.last_event) return null
  const { text } = humanizeEvent(loop.last_event)
  const m = text.match(/^Blocked\s*[—-]\s*(.*)/)
  return m ? m[1] : text
}

/* ---------- status visuals ---------- */

const STATUS: Record<string, { label: string; pill: string; accent: string }> = {
  running: {
    label: 'In progress',
    pill: 'bg-sky-500/10 text-sky-300 ring-sky-500/30',
    accent: 'border-l-sky-500',
  },
  blocked: {
    label: 'Blocked',
    pill: 'bg-amber-500/10 text-amber-300 ring-amber-500/30',
    accent: 'border-l-amber-500',
  },
  done: {
    label: 'Done',
    pill: 'bg-emerald-500/10 text-emerald-300 ring-emerald-500/30',
    accent: 'border-l-emerald-500',
  },
}

function st(status: string) {
  return STATUS[status] ?? {
    label: status,
    pill: 'bg-neutral-500/10 text-neutral-300 ring-neutral-500/30',
    accent: 'border-l-neutral-600',
  }
}

const WAVE_LABEL: Record<string, string> = {
  pending: 'Pending',
  'in-progress': 'In progress',
  done: 'Done',
}

function WaveDot({ status }: { status: string }) {
  const cls =
    status === 'done'
      ? 'bg-emerald-400'
      : status === 'in-progress'
        ? 'bg-sky-400 animate-pulse'
        : 'bg-neutral-700'
  return <span className={`inline-block w-2 h-2 rounded-full ${cls}`} />
}

const GATE_LABEL: Record<string, string> = {
  pending: 'Pending',
  met: 'Met',
  waived: 'Waived',
  failed: 'Failed',
}

function gateTone(status: string) {
  if (status === 'met') return 'text-emerald-300'
  if (status === 'waived') return 'text-violet-300'
  if (status === 'failed') return 'text-red-300'
  return 'text-neutral-400'
}

/* ---------- components ---------- */

function StatCard({ label, value, tone }: { label: string; value: number; tone: string }) {
  return (
    <div className="rounded-lg border border-neutral-800 bg-neutral-900/60 px-4 py-3">
      <div className={`text-2xl font-semibold ${tone}`}>{value}</div>
      <div className="text-[11px] uppercase tracking-wider text-neutral-500 mt-0.5">{label}</div>
    </div>
  )
}

function LoopRow({
  loop, detail, open, onToggle,
}: {
  loop: LoopSummary
  detail: LoopDetail | null
  open: boolean
  onToggle: () => void
}) {
  const s = st(loop.status)
  const reason = blockReason(loop)
  const waveEntries = detail
    ? Object.entries(detail.waves).sort((a, b) => Number(a[0]) - Number(b[0]))
    : []
  const gateEntries = detail ? Object.entries(detail.gates).sort() : []
  const pct = loop.waves_total ? Math.round((loop.waves_done / loop.waves_total) * 100) : 0

  return (
    <div className={`rounded-xl border border-neutral-800 border-l-2 ${s.accent} bg-neutral-900/60 overflow-hidden`}>
      {/* summary row */}
      <button onClick={onToggle} className="w-full text-left px-4 py-3.5 hover:bg-neutral-800/30 transition-colors">
        <div className="flex items-center gap-4">
          <div className="min-w-0 flex-1">
            <div className="flex items-baseline gap-2 flex-wrap">
              <span className="text-[15px] font-semibold text-neutral-100">{loop.feature}</span>
              <span className="text-xs text-neutral-500 font-mono">{loop.repo}</span>
            </div>
            <div className="mt-1 flex items-center gap-3 text-xs text-neutral-500">
              <span>{loop.waves_done} of {loop.waves_total} waves</span>
              {loop.gates_total > 0 && (
                <span className={loop.gates_pending > 0 ? 'text-amber-400/90' : ''}>
                  {loop.gates_total - loop.gates_pending} of {loop.gates_total} gates
                </span>
              )}
              <span>·</span>
              <span>{loop.iterations} iteration{loop.iterations === 1 ? '' : 's'}</span>
              <span>·</span>
              <span>updated {fmtAgo(loop.updated)}</span>
            </div>
          </div>

          <div className="hidden sm:flex flex-col items-end gap-1.5 shrink-0">
            <span className={`px-2.5 py-1 rounded-full text-xs font-medium ring-1 ${s.pill}`}>
              {s.label}
            </span>
            <div className="w-28 h-1 rounded-full bg-neutral-800 overflow-hidden">
              <div
                className={`h-full rounded-full bg-gradient-to-r ${
                  loop.status === 'running' ? 'from-sky-500 to-cyan-400'
                  : loop.status === 'blocked' ? 'from-amber-500 to-orange-400'
                  : 'from-emerald-500 to-teal-400'
                } transition-all duration-700`}
                style={{ width: `${loop.status === 'done' ? 100 : pct}%` }}
              />
            </div>
          </div>
        </div>

        {reason && (
          <div className="mt-2.5 rounded-md bg-amber-500/10 ring-1 ring-amber-500/20 px-3 py-2">
            <p className="text-xs text-amber-200/90 leading-relaxed">
              <span className="font-medium">Waiting on a human:</span> {reason}
            </p>
          </div>
        )}

        <div className="mt-2 flex items-center gap-1.5 text-neutral-600">
          <svg className={`w-3 h-3 transition-transform ${open ? 'rotate-90' : ''}`} viewBox="0 0 12 12" fill="currentColor">
            <path d="M4 2l4 4-4 4V2z" />
          </svg>
          <span className="text-[11px]">{open ? 'Hide details' : 'Show details'}</span>
        </div>
      </button>

      {/* detail panel */}
      {open && (
        <div className="border-t border-neutral-800 px-4 py-4 bg-neutral-950/50">
          {!detail && <p className="text-xs text-neutral-500">Loading…</p>}

          {detail && (
            <div className="grid gap-6 lg:grid-cols-2">
              {/* left: waves + gates */}
              <div className="space-y-6 min-w-0">
                {waveEntries.length > 0 && (
                  <section>
                    <h3 className="text-xs font-semibold uppercase tracking-wider text-neutral-500 mb-2.5">
                      Waves
                    </h3>
                    <div className="rounded-lg border border-neutral-800 divide-y divide-neutral-800/70">
                      {waveEntries.map(([n, w]) => (
                        <div key={n} className="px-3 py-2.5 flex items-start gap-3">
                          <div className="w-8 shrink-0 pt-0.5">
                            <span className="text-xs font-mono text-neutral-500">w{n}</span>
                          </div>
                          <div className="min-w-0 flex-1">
                            <div className="flex items-center gap-2">
                              <WaveDot status={w.status} />
                              <span className="text-xs text-neutral-300">{WAVE_LABEL[w.status] ?? w.status}</span>
                              <span className="text-[11px] font-mono text-neutral-600">{w.branch}</span>
                              {w.pr && w.pr !== '—' && (
                                <span className="text-[11px] font-mono text-neutral-500">PR {w.pr}</span>
                              )}
                              <span className="ml-auto text-[11px] text-neutral-600 shrink-0">
                                {fmtDateTime(w.updated)}
                              </span>
                            </div>
                            {w.evidence && w.evidence !== '—' && (
                              <p className="mt-1 text-[11px] text-neutral-500 leading-relaxed">{w.evidence}</p>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  </section>
                )}

                {gateEntries.length > 0 && (
                  <section>
                    <h3 className="text-xs font-semibold uppercase tracking-wider text-neutral-500 mb-2.5">
                      Gates
                    </h3>
                    <div className="rounded-lg border border-neutral-800 divide-y divide-neutral-800/70">
                      {gateEntries.map(([gid, g]) => (
                        <div key={gid} className="px-3 py-2.5 flex items-start gap-3">
                          <span className="w-8 shrink-0 text-xs font-mono text-neutral-400 pt-px">{gid}</span>
                          <div className="min-w-0 flex-1">
                            <span className={`text-xs font-medium ${gateTone(g.status)}`}>
                              {GATE_LABEL[g.status] ?? g.status}
                            </span>
                            {g.evidence && g.evidence !== '—' && (
                              <p className="mt-0.5 text-[11px] text-neutral-500 leading-relaxed">{g.evidence}</p>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  </section>
                )}
              </div>

              {/* right: event timeline */}
              {detail.events.length > 0 && (
                <section className="min-w-0">
                  <h3 className="text-xs font-semibold uppercase tracking-wider text-neutral-500 mb-2.5">
                    History <span className="text-neutral-600 font-normal">({detail.events.length} events)</span>
                  </h3>
                  <ol className="relative border-l border-neutral-800 ml-1.5 space-y-3">
                    {[...detail.events].reverse().map((e, i) => {
                      const { ts, text } = humanizeEvent(e)
                      return (
                        <li key={i} className="relative pl-4">
                          <span className={`absolute -left-[3.5px] top-[7px] w-1.5 h-1.5 rounded-full ${
                            i === 0 ? 'bg-sky-400' : 'bg-neutral-700'
                          }`} />
                          <div className="text-[11px] leading-relaxed">
                            <span className="text-neutral-500">{text}</span>
                            <span className="block text-neutral-600 font-mono text-[10px] mt-0.5">
                              {fmtDateTime(ts)}
                            </span>
                          </div>
                        </li>
                      )
                    })}
                  </ol>
                </section>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

/* ---------- page ---------- */

export default function Loops() {
  const [loops, setLoops] = useState<LoopSummary[]>([])
  const [live, setLive] = useState(false)
  const [filter, setFilter] = useState<Filter>('all')
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
        for (const key of Object.keys(detailsRef.current)) {
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

  const counts = useMemo(() => ({
    running: loops.filter((l) => l.status === 'running').length,
    blocked: loops.filter((l) => l.status === 'blocked').length,
    done: loops.filter((l) => l.status === 'done').length,
  }), [loops])

  const visible = useMemo(() => {
    const filtered = loops.filter((l) =>
      filter === 'all' ? true
      : filter === 'attention' ? l.status === 'blocked'
      : filter === 'running' ? l.status === 'running'
      : l.status === 'done',
    )
    const order: Record<string, number> = { running: 0, blocked: 1, done: 2 }
    return [...filtered].sort(
      (a, b) => (order[a.status] ?? 3) - (order[b.status] ?? 3) || b.updated.localeCompare(a.updated),
    )
  }, [loops, filter])

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
    <div className="space-y-6 max-w-5xl">
      {/* header */}
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <div className="flex items-center gap-3">
            <h2 className="text-xl font-semibold text-neutral-100">Delivery Loops</h2>
            <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[11px] font-medium ring-1 ${
              live
                ? 'bg-emerald-500/10 text-emerald-300 ring-emerald-500/30'
                : 'bg-neutral-800 text-neutral-400 ring-neutral-700'
            }`}>
              <span className={`w-1.5 h-1.5 rounded-full ${live ? 'bg-emerald-400 animate-pulse' : 'bg-neutral-500'}`} />
              {live ? 'Live' : 'Reconnecting'}
            </span>
          </div>
          <p className="text-sm text-neutral-500 mt-1">
            Autonomous feature delivery across your repos — waves, gates, and history, updated in real time.
          </p>
        </div>
      </div>

      {/* stats */}
      <div className="grid grid-cols-3 gap-3 max-w-md">
        <StatCard label="In progress" value={counts.running} tone="text-sky-300" />
        <StatCard label="Needs you" value={counts.blocked} tone="text-amber-300" />
        <StatCard label="Done" value={counts.done} tone="text-emerald-300" />
      </div>

      {/* filters */}
      <div className="flex gap-1 border-b border-neutral-800">
        {FILTERS.map((f) => (
          <button
            key={f.key}
            onClick={() => setFilter(f.key)}
            className={`px-3 py-2 text-sm transition-colors border-b-2 -mb-px ${
              filter === f.key
                ? 'border-sky-500 text-neutral-100'
                : 'border-transparent text-neutral-500 hover:text-neutral-300'
            }`}
          >
            {f.label}
            {f.key === 'attention' && counts.blocked > 0 && (
              <span className="ml-1.5 text-[11px] font-mono text-amber-400">{counts.blocked}</span>
            )}
          </button>
        ))}
      </div>

      {/* list */}
      {visible.length === 0 && (
        <div className="rounded-xl border border-dashed border-neutral-800 p-12 text-center">
          <p className="text-sm text-neutral-500">
            {loops.length === 0 ? 'No delivery loops yet.' : 'Nothing in this view.'}
          </p>
          {loops.length === 0 && (
            <p className="text-xs text-neutral-600 mt-1.5 font-mono">
              loops appear once a feature has specs/&lt;feature&gt;/LOOP.state.json
            </p>
          )}
        </div>
      )}

      <div className="space-y-3">
        {visible.map((l) => {
          const key = `${l.repo}/${l.feature}`
          return (
            <LoopRow
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
