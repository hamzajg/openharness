import { useEffect, useMemo, useState } from 'react'
import { api, type Evolution, type EvolutionCommit } from '../api'
import { dayKey, fmtDate, fmtDateTime } from '../lib/format'
import {
  Card,
  EmptyState,
  ErrorNote,
  Loading,
  SectionTitle,
  SegmentedControl,
  StatCard,
  cn,
} from './ui'

/* ---------- visuals ---------- */

const TYPE_STYLE: Record<string, { dot: string; label: string }> = {
  feature:  { dot: 'bg-sky-400',      label: 'feat' },
  fix:      { dot: 'bg-amber-400',    label: 'fix' },
  evolve:   { dot: 'bg-violet-400',   label: 'evolve' },
  docs:     { dot: 'bg-ink-mute',     label: 'docs' },
  chore:    { dot: 'bg-ink-faint',    label: 'chore' },
  refactor: { dot: 'bg-cyan-400',     label: 'refactor' },
  other:    { dot: 'bg-line-strong',  label: 'commit' },
}

function typeStyle(t: string) {
  return TYPE_STYLE[t] ?? TYPE_STYLE.other
}

const TYPE_FILTERS = ['all', 'feature', 'fix', 'evolve', 'docs'] as const

/* ---------- components ---------- */

function CommitRow({ c }: { c: EvolutionCommit }) {
  const t = typeStyle(c.type)
  return (
    <div className="flex items-start gap-3 py-2">
      <span className={cn('mt-1.5 h-2 w-2 shrink-0 rounded-full', t.dot)} />
      <div className="min-w-0 flex-1">
        <p className="text-sm leading-snug text-ink-body">{c.subject}</p>
        <p className="mt-0.5 font-mono text-[11px] text-ink-faint">
          {c.sha} · {fmtDateTime(c.date)}
        </p>
      </div>
      <span className="shrink-0 pt-0.5 font-mono text-[10px] uppercase tracking-wider text-ink-faint">
        {t.label}
      </span>
    </div>
  )
}

/* ---------- maturity dashboard (embedded in SELF) ---------- */

export default function Maturity() {
  const [data, setData] = useState<Evolution | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [typeFilter, setTypeFilter] = useState<string>('all')

  useEffect(() => {
    api.evolution().then(setData).catch((e) => setErr(e?.message || 'Failed to load'))
  }, [])

  const commits = useMemo(() => {
    const all = data?.commits ?? []
    const filtered = typeFilter === 'all' ? all : all.filter((c) => c.type === typeFilter)
    // group by day, preserving order (git log is newest-first)
    const groups: { day: string; items: EvolutionCommit[] }[] = []
    for (const c of filtered) {
      const k = dayKey(c.date)
      const last = groups[groups.length - 1]
      if (last && last.day === k) last.items.push(c)
      else groups.push({ day: k, items: [c] })
    }
    return groups
  }, [data, typeFilter])

  const typeCounts = useMemo(() => {
    const counts: Record<string, number> = { all: data?.commits.length ?? 0 }
    for (const c of data?.commits ?? []) counts[c.type] = (counts[c.type] ?? 0) + 1
    return counts
  }, [data])

  if (err) return <ErrorNote>{err}</ErrorNote>
  if (!data) return <Loading label="Loading maturity…" />

  const s = data.stats
  const corePct = Math.round((s.core_loc / s.core_budget) * 100)
  const platformPct = Math.round((s.platform_loc / s.platform_budget) * 100)

  return (
    <div className="space-y-6">
      {/* maturity stats */}
      <section>
        <SectionTitle>Maturity</SectionTitle>
        <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
          <StatCard label="Decisions" value={data.decisions.length} sub="D001–D0NN binding" />
          <StatCard label="Skills" value={s.skills} sub={`${s.skills_loc} LOC`} />
          <StatCard label="Blocks" value={s.blocks} sub="SELF/blocks specs" />
          <StatCard label="Tests" value={s.tests} sub="pytest cases" />
          <StatCard
            label="Core LOC"
            value={`${s.core_loc}/${s.core_budget}`}
            tone={s.core_loc > s.core_budget ? 'text-amber-300' : 'text-emerald-300'}
            sub={s.core_loc > s.core_budget ? 'over D012 budget' : 'within D012 budget'}
            bar={{ pct: corePct, over: s.core_loc > s.core_budget }}
          />
          <StatCard
            label="Platform LOC"
            value={`${s.platform_loc}/${s.platform_budget}`}
            tone={s.platform_loc > s.platform_budget ? 'text-amber-300' : 'text-ink'}
            sub="repos + metrics + observers + serve (D012)"
            bar={{ pct: platformPct, over: s.platform_loc > s.platform_budget }}
          />
        </div>
      </section>

      {/* decision log */}
      <section>
        <SectionTitle>
          Decision log <span className="font-normal text-ink-faint">— binding precedent (PRINCIPLES.md)</span>
        </SectionTitle>
        <div className="grid gap-3 md:grid-cols-2">
          {data.decisions.map((d) => (
            <Card key={d.id} className="p-4">
              <div className="mb-1.5 flex items-baseline gap-2">
                <span className="font-mono text-[11px] font-semibold text-sky-400">{d.id}</span>
                <span className="text-sm font-medium text-ink">{d.title}</span>
              </div>
              {d.rule && (
                <p className="text-xs leading-relaxed text-ink-body">
                  <span className="font-medium text-ink-faint">Rule: </span>{d.rule}
                </p>
              )}
              {d.because && (
                <p className="mt-1.5 text-xs leading-relaxed text-ink-mute">
                  <span className="font-medium text-ink-faint">Because: </span>{d.because}
                </p>
              )}
            </Card>
          ))}
        </div>
      </section>

      {/* commit history */}
      <section>
        <div className="mb-2.5 flex flex-wrap items-center justify-between gap-2">
          <SectionTitle>
            Change history <span className="font-normal text-ink-faint">— harness self-evolution</span>
          </SectionTitle>
          <SegmentedControl
            value={typeFilter}
            onChange={setTypeFilter}
            options={TYPE_FILTERS.map((t) => ({
              value: t,
              label: t === 'all' ? 'All' : TYPE_STYLE[t]?.label ?? t,
              count: typeCounts[t] ?? 0,
            }))}
          />
        </div>

        {commits.length === 0 ? (
          <EmptyState title="No commits in this view." />
        ) : (
          <Card className="divide-y divide-line/60 px-4 py-2">
            {commits.map((g) => (
              <div key={g.day}>
                <div className="pb-1 pt-3 text-[11px] font-semibold uppercase tracking-wider text-ink-faint">
                  {fmtDate(g.items[0].date)}
                </div>
                {g.items.map((c) => <CommitRow key={c.sha} c={c} />)}
              </div>
            ))}
          </Card>
        )}
      </section>
    </div>
  )
}
