import { useEffect, useMemo, useRef, useState } from 'react'
import { api, LoopDetail, LoopSummary } from '../api'
import { fmtDateTime, relTime } from '../lib/format'
import {
  Badge,
  Button,
  Drawer,
  EmptyState,
  ListCard,
  LiveBadge,
  SectionTitle,
  SegmentedControl,
  StatCard,
  Toolbar,
  cn,
} from '../components/ui'
import { IconChevronRight } from '../components/icons'
import {
  GATE_LABEL,
  WAVE_LABEL,
  blockReason,
  gateTone,
  humanizeEvent,
  loopStatus,
  waveDotClass,
} from '../lib/loops'

type Filter = 'all' | 'attention' | 'running' | 'done'

/* ------------------------------------------------------------ list */

function LoopRow({
  loop,
  selected,
  onSelect,
}: {
  loop: LoopSummary
  selected: boolean
  onSelect: () => void
}) {
  const status = loopStatus(loop.status)
  const reason = blockReason(loop)
  const pct = loop.waves_total ? Math.round((loop.waves_done / loop.waves_total) * 100) : 0

  return (
    <button
      onClick={onSelect}
      className={cn(
        'group w-full cursor-pointer overflow-hidden rounded-xl border border-l-2 bg-surface/60 text-left transition-colors',
        status.accent,
        selected
          ? 'border-line ring-1 ring-accent/30'
          : 'border-line hover:bg-line/30',
      )}
    >
      <div className="px-4 py-3.5">
        <div className="flex items-center gap-4">
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-baseline gap-2">
              <span className="text-[15px] font-semibold text-ink">{loop.feature}</span>
              <span className="font-mono text-xs text-ink-mute">{loop.repo}</span>
            </div>
            <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-ink-mute">
              <span>
                {loop.waves_done}/{loop.waves_total} waves
              </span>
              {loop.gates_total > 0 && (
                <span className={loop.gates_pending > 0 ? 'text-warn' : ''}>
                  · {loop.gates_total - loop.gates_pending}/{loop.gates_total} gates
                </span>
              )}
              <span className="hidden sm:inline">
                · {loop.iterations} iter · {relTime(loop.updated)}
              </span>
            </div>
          </div>

          <div className="flex shrink-0 flex-col items-end gap-1.5">
            <Badge tone={status.tone}>{status.label}</Badge>
            <IconChevronRight
              className={cn(
                'h-3.5 w-3.5 transition-colors',
                selected ? 'text-accent' : 'text-ink-faint group-hover:text-ink-dim',
              )}
            />
            <div
              aria-hidden="true"
              className="hidden h-1 w-28 overflow-hidden rounded-full bg-line sm:block"
            >
              <div
                className={cn(
                  'h-full rounded-full transition-all duration-700',
                  loop.status === 'running'
                    ? 'bg-accent'
                    : loop.status === 'blocked'
                      ? 'bg-warn'
                      : 'bg-ok',
                )}
                style={{ width: `${loop.status === 'done' ? 100 : pct}%` }}
              />
            </div>
          </div>
        </div>

        {reason && (
          <div className="mt-2.5 rounded-md bg-warn/10 px-3 py-2 ring-1 ring-warn/20">
            <p className="text-xs leading-relaxed text-warn">
              <span className="font-medium">Waiting on a human:</span> {reason}
            </p>
          </div>
        )}
      </div>
    </button>
  )
}

/* ---------------------------------------------------------- drawer */

function LoopDrawer({
  loop,
  detail,
  onClose,
}: {
  loop: LoopSummary
  detail: LoopDetail | null
  onClose: () => void
}) {
  const status = loopStatus(loop.status)
  const waves = detail
    ? Object.entries(detail.waves).sort((a, b) => Number(a[0]) - Number(b[0]))
    : []
  const gates = detail ? Object.entries(detail.gates).sort() : []

  return (
    <Drawer
      open
      onClose={onClose}
      title={loop.feature}
      subtitle={`${loop.repo} · specs/${loop.feature}`}
      accent={status.accent}
      wide
      headerExtra={<Badge tone={status.tone}>{status.label}</Badge>}
      meta={
        <>
          <span>
            {loop.waves_done} of {loop.waves_total} waves
          </span>
          {loop.gates_total > 0 && (
            <span className={loop.gates_pending > 0 ? 'text-warn' : ''}>
              {loop.gates_total - loop.gates_pending} of {loop.gates_total} gates met
            </span>
          )}
          <span>{loop.iterations} iteration{loop.iterations === 1 ? '' : 's'}</span>
          <span>updated {relTime(loop.updated)}</span>
        </>
      }
    >
      {!detail ? (
        <p className="text-sm text-ink-mute">Loading…</p>
      ) : (
        <div className="space-y-6">
          {waves.length > 0 && (
            <section>
              <SectionTitle>Waves</SectionTitle>
              <ListCard>
                {waves.map(([n, w]) => (
                  <div key={n} className="flex items-start gap-3 px-3 py-2.5">
                    <span className="w-7 shrink-0 pt-px font-mono text-xs text-ink-mute">
                      w{n}
                    </span>
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span
                          className={cn('h-2 w-2 rounded-full', waveDotClass(w.status))}
                        />
                        <span className="text-xs text-ink-body">
                          {WAVE_LABEL[w.status] ?? w.status}
                        </span>
                        <span className="font-mono text-[11px] text-ink-faint">{w.branch}</span>
                        {w.pr && w.pr !== '—' && (
                          <span className="font-mono text-[11px] text-ink-mute">PR {w.pr}</span>
                        )}
                        <span className="ml-auto shrink-0 text-[11px] text-ink-faint">
                          {fmtDateTime(w.updated)}
                        </span>
                      </div>
                      {w.evidence && w.evidence !== '—' && (
                        <p className="mt-1 text-[11px] leading-relaxed text-ink-mute">
                          {w.evidence}
                        </p>
                      )}
                    </div>
                  </div>
                ))}
              </ListCard>
            </section>
          )}

          {gates.length > 0 && (
            <section>
              <SectionTitle>Gates</SectionTitle>
              <ListCard>
                {gates.map(([id, g]) => (
                  <div key={id} className="flex items-start gap-3 px-3 py-2.5">
                    <span className="w-7 shrink-0 pt-px font-mono text-xs text-ink-dim">{id}</span>
                    <div className="min-w-0 flex-1">
                      <span className={cn('text-xs font-medium', gateTone(g.status))}>
                        {GATE_LABEL[g.status] ?? g.status}
                      </span>
                      {g.evidence && g.evidence !== '—' && (
                        <p className="mt-0.5 text-[11px] leading-relaxed text-ink-mute">
                          {g.evidence}
                        </p>
                      )}
                    </div>
                  </div>
                ))}
              </ListCard>
            </section>
          )}

          {detail.events.length > 0 && (
            <section>
              <SectionTitle count={detail.events.length}>History</SectionTitle>
              <ol className="relative ml-1.5 space-y-3 border-l border-line">
                {[...detail.events].reverse().map((event, i) => {
                  const { ts, text } = humanizeEvent(event)
                  return (
                    <li key={i} className="relative pl-4">
                      <span
                        className={cn(
                          'absolute -left-[3.5px] top-[7px] h-1.5 w-1.5 rounded-full',
                          i === 0 ? 'bg-accent' : 'bg-line-strong',
                        )}
                      />
                      <div className="text-[11px] leading-relaxed">
                        <span className="text-ink-mute">{text}</span>
                        <span className="mt-0.5 block font-mono text-[10px] text-ink-faint">
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
    </Drawer>
  )
}

/* ------------------------------------------------------------ page */

const ORDER: Record<string, number> = { running: 0, blocked: 1, done: 2 }

export default function Loops() {
  const [loops, setLoops] = useState<LoopSummary[]>([])
  const [live, setLive] = useState(false)
  const [filter, setFilter] = useState<Filter>('all')
  const [openKey, setOpenKey] = useState<string | null>(null)
  const [details, setDetails] = useState<Record<string, LoopDetail>>({})
  const openDetails = useRef(details)
  openDetails.current = details

  useEffect(() => {
    let cancelled = false
    api
      .loops()
      .then((r) => {
        if (!cancelled) setLoops(r.loops)
      })
      .catch(() => {})

    const es = new EventSource('/api/loops/stream')
    es.addEventListener('open', () => setLive(true))
    es.addEventListener('loops', (ev: MessageEvent) => {
      try {
        const next: LoopSummary[] = JSON.parse(ev.data)
        setLoops(next)
        // Refresh any detail pane whose loop still exists.
        for (const key of Object.keys(openDetails.current)) {
          const slash = key.indexOf('/')
          const repo = key.slice(0, slash)
          const feature = key.slice(slash + 1)
          if (!next.some((l) => l.repo === repo && l.feature === feature)) continue
          api
            .loopDetail(repo, feature)
            .then((d) => setDetails((p) => ({ ...p, [key]: d })))
            .catch(() => {})
        }
      } catch {}
    })
    es.onerror = () => setLive(false)
    return () => {
      cancelled = true
      es.close()
    }
  }, [])

  const counts = useMemo(
    () => ({
      all: loops.length,
      running: loops.filter((l) => l.status === 'running').length,
      blocked: loops.filter((l) => l.status === 'blocked').length,
      done: loops.filter((l) => l.status === 'done').length,
    }),
    [loops],
  )

  const visible = useMemo(() => {
    const filtered = loops.filter((l) =>
      filter === 'all'
        ? true
        : filter === 'attention'
          ? l.status === 'blocked'
          : filter === 'running'
            ? l.status === 'running'
            : l.status === 'done',
    )
    return [...filtered].sort(
      (a, b) => (ORDER[a.status] ?? 3) - (ORDER[b.status] ?? 3) || b.updated.localeCompare(a.updated),
    )
  }, [loops, filter])

  const openLoop = openKey
    ? (loops.find((l) => `${l.repo}/${l.feature}` === openKey) ?? null)
    : null

  const select = (l: LoopSummary) => {
    const key = `${l.repo}/${l.feature}`
    setOpenKey((cur) => (cur === key ? null : key))
    if (!details[key]) {
      api
        .loopDetail(l.repo, l.feature)
        .then((d) => setDetails((p) => ({ ...p, [key]: d })))
        .catch(() => {})
    }
  }

  return (
    <div className="space-y-6">
      <Toolbar className="justify-between">
        <div className="grid max-w-md flex-1 grid-cols-3 gap-3">
          <StatCard label="In progress" value={counts.running} tone="text-info" />
          <StatCard label="Needs you" value={counts.blocked} tone="text-warn" />
          <StatCard label="Done" value={counts.done} tone="text-ok" />
        </div>
        <LiveBadge live={live} label={live ? 'Live' : 'Reconnecting'} />
      </Toolbar>

      <SegmentedControl<Filter>
        label="Filter loops"
        value={filter}
        onChange={setFilter}
        options={[
          { value: 'all', label: 'All', count: counts.all },
          { value: 'attention', label: 'Needs you', count: counts.blocked },
          { value: 'running', label: 'In progress', count: counts.running },
          { value: 'done', label: 'Done', count: counts.done },
        ]}
      />

      {visible.length === 0 ? (
        <EmptyState
          title={loops.length === 0 ? 'No delivery loops yet.' : 'Nothing in this view.'}
          hint={
            loops.length === 0
              ? 'loops appear once a feature has specs/<feature>/LOOP.state.json'
              : undefined
          }
          action={
            loops.length > 0 ? (
              <Button variant="secondary" size="sm" onClick={() => setFilter('all')}>
                Clear filter
              </Button>
            ) : undefined
          }
        />
      ) : (
        <div className="space-y-3">
          {visible.map((l) => {
            const key = `${l.repo}/${l.feature}`
            return (
              <LoopRow
                key={key}
                loop={l}
                selected={openKey === key}
                onSelect={() => select(l)}
              />
            )
          })}
        </div>
      )}

      {openLoop && openKey && (
        <LoopDrawer
          loop={openLoop}
          detail={details[openKey] ?? null}
          onClose={() => setOpenKey(null)}
        />
      )}
    </div>
  )
}
