import { useEffect, useMemo, useState } from 'react'
import { api, type Evolution, type EvolutionCommit } from '../api'

/* ---------- formatting ---------- */

function fmtDate(iso: string) {
  const t = Date.parse(iso)
  if (!t) return ''
  return new Date(t).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })
}

function fmtDateTime(iso: string) {
  const t = Date.parse(iso)
  if (!t) return iso
  return new Date(t).toLocaleString(undefined, {
    month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
  })
}

function dayKey(iso: string) {
  const t = Date.parse(iso)
  return t ? new Date(t).toDateString() : iso
}

/* ---------- visuals ---------- */

const TYPE_STYLE: Record<string, { dot: string; label: string }> = {
  feature:  { dot: 'bg-sky-400',     label: 'feat' },
  fix:      { dot: 'bg-amber-400',   label: 'fix' },
  evolve:   { dot: 'bg-violet-400',  label: 'evolve' },
  docs:     { dot: 'bg-neutral-500', label: 'docs' },
  chore:    { dot: 'bg-neutral-600', label: 'chore' },
  refactor: { dot: 'bg-cyan-400',    label: 'refactor' },
  other:    { dot: 'bg-neutral-700', label: 'commit' },
}

function typeStyle(t: string) {
  return TYPE_STYLE[t] ?? TYPE_STYLE.other
}

const TYPE_FILTERS = ['all', 'feature', 'fix', 'evolve', 'docs'] as const

/* ---------- components ---------- */

function StatCard({ label, value, sub, tone, bar }: {
  label: string; value: string | number; sub?: string; tone?: string
  bar?: { pct: number; over?: boolean }
}) {
  return (
    <div className="rounded-lg border border-neutral-800 bg-neutral-900/60 px-4 py-3">
      <div className={`text-xl font-semibold ${tone ?? 'text-neutral-100'}`}>{value}</div>
      <div className="text-[11px] uppercase tracking-wider text-neutral-500 mt-0.5">{label}</div>
      {sub && <div className="text-[11px] text-neutral-600 mt-1">{sub}</div>}
      {bar && (
        <div className="mt-2 h-1 rounded-full bg-neutral-800 overflow-hidden">
          <div
            className={`h-full rounded-full ${bar.over ? 'bg-amber-500' : 'bg-emerald-500'}`}
            style={{ width: `${Math.min(100, bar.pct)}%` }}
          />
        </div>
      )}
    </div>
  )
}

function CommitRow({ c }: { c: EvolutionCommit }) {
  const t = typeStyle(c.type)
  return (
    <div className="flex items-start gap-3 py-2">
      <span className={`mt-1.5 w-2 h-2 rounded-full shrink-0 ${t.dot}`} />
      <div className="min-w-0 flex-1">
        <p className="text-sm text-neutral-300 leading-snug">{c.subject}</p>
        <p className="text-[11px] text-neutral-600 font-mono mt-0.5">
          {c.sha} · {fmtDateTime(c.date)}
        </p>
      </div>
      <span className="text-[10px] font-mono uppercase tracking-wider text-neutral-600 shrink-0 pt-0.5">
        {t.label}
      </span>
    </div>
  )
}

/* ---------- page ---------- */

export default function Evolution() {
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

  const s = data?.stats
  const corePct = s ? Math.round((s.core_loc / s.core_budget) * 100) : 0
  const platformPct = s ? Math.round((s.platform_loc / s.platform_budget) * 100) : 0

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold text-neutral-100">Evolution</h2>
        <p className="text-sm text-neutral-500 mt-1">
          How the harness matured — binding decisions, self-applied changes, and health budgets.
        </p>
      </div>

      {err && <div className="text-sm text-red-400">{err}</div>}
      {!data && !err && <p className="text-sm text-neutral-500">Loading…</p>}

      {data && s && (
        <>
          {/* maturity stats */}
          <div>
            <h3 className="text-xs font-semibold uppercase tracking-wider text-neutral-500 mb-2.5">
              Maturity
            </h3>
            <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-3">
              <StatCard label="Decisions" value={data.decisions.length} sub="D001–D0NN binding" />
              <StatCard label="Skills" value={s.skills} sub={`${s.skills_loc} LOC`} />
              <StatCard label="Blocks" value={s.blocks} sub="SELF/blocks specs" />
              <StatCard label="Tests" value={s.tests} sub="pytest cases" />
              <StatCard
                label="Core LOC"
                value={`${s.core_loc}/${s.core_budget}`}
                tone={s.core_loc > s.core_budget ? 'text-amber-300' : 'text-emerald-300'}
                sub={s.core_loc > s.core_budget ? 'over D003 budget' : 'within D003 budget'}
                bar={{ pct: corePct, over: s.core_loc > s.core_budget }}
              />
              <StatCard
                label="Platform LOC"
                value={`${s.platform_loc}/${s.platform_budget}`}
                tone={s.platform_loc > s.platform_budget ? 'text-amber-300' : 'text-neutral-100'}
                sub="repos + metrics + observers + serve (D012)"
                bar={{ pct: platformPct, over: s.platform_loc > s.platform_budget }}
              />
            </div>
          </div>

          {/* decision log */}
          <div>
            <h3 className="text-xs font-semibold uppercase tracking-wider text-neutral-500 mb-2.5">
              Decision log <span className="text-neutral-600 font-normal">— binding precedent (PRINCIPLES.md)</span>
            </h3>
            <div className="grid gap-3 md:grid-cols-2">
              {data.decisions.map((d) => (
                <div key={d.id} className="rounded-xl border border-neutral-800 bg-neutral-900/60 p-4">
                  <div className="flex items-baseline gap-2 mb-1.5">
                    <span className="text-[11px] font-mono font-semibold text-sky-400">{d.id}</span>
                    <span className="text-sm font-medium text-neutral-100">{d.title}</span>
                  </div>
                  {d.rule && (
                    <p className="text-xs text-neutral-400 leading-relaxed">
                      <span className="text-neutral-600 font-medium">Rule: </span>{d.rule}
                    </p>
                  )}
                  {d.because && (
                    <p className="text-xs text-neutral-500 leading-relaxed mt-1.5">
                      <span className="text-neutral-600 font-medium">Because: </span>{d.because}
                    </p>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* commit history */}
          <div>
            <div className="flex items-center justify-between mb-2.5 flex-wrap gap-2">
              <h3 className="text-xs font-semibold uppercase tracking-wider text-neutral-500">
                Change history <span className="text-neutral-600 font-normal">— harness self-evolution</span>
              </h3>
              <div className="flex gap-1">
                {TYPE_FILTERS.map((t) => (
                  <button
                    key={t}
                    onClick={() => setTypeFilter(t)}
                    className={`px-2.5 py-1 rounded-md text-[11px] font-medium transition-colors ${
                      typeFilter === t
                        ? 'bg-neutral-800 text-neutral-100'
                        : 'text-neutral-500 hover:text-neutral-300 hover:bg-neutral-800/50'
                    }`}
                  >
                    {t === 'all' ? 'All' : TYPE_STYLE[t]?.label ?? t}
                    <span className="ml-1 text-neutral-600 font-mono">{typeCounts[t] ?? 0}</span>
                  </button>
                ))}
              </div>
            </div>

            <div className="rounded-xl border border-neutral-800 bg-neutral-900/60 px-4 py-2 divide-y divide-neutral-800/50">
              {commits.length === 0 && (
                <p className="text-sm text-neutral-500 py-6 text-center">No commits in this view.</p>
              )}
              {commits.map((g) => (
                <div key={g.day}>
                  <div className="pt-3 pb-1 text-[11px] font-semibold uppercase tracking-wider text-neutral-600">
                    {fmtDate(g.items[0].date)}
                  </div>
                  {g.items.map((c) => <CommitRow key={c.sha} c={c} />)}
                </div>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  )
}
