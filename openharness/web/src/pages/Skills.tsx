import { useEffect, useMemo, useState } from 'react'
import { api, Skill } from '../api'

export default function Skills() {
  const [skills, setSkills] = useState<Skill[]>([])
  const [err, setErr] = useState<string | null>(null)
  const [open, setOpen] = useState<Record<string, Record<string, string>>>({})
  const [running, setRunning] = useState<string | null>(null)
  const [result, setResult] = useState<Record<string, string>>({})
  const [query, setQuery] = useState('')

  useEffect(() => {
    api.skills().then(setSkills).catch((e) => setErr(e?.message || 'Failed to load skills'))
  }, [])

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q) return skills
    return skills.filter(
      (s) => s.name.toLowerCase().includes(q) || s.description.toLowerCase().includes(q),
    )
  }, [skills, query])

  const nonDet = skills.filter((s) => s.non_deterministic).length

  const update = (name: string, k: string, v: string) =>
    setOpen((prev) => ({ ...prev, [name]: { ...(prev[name] || {}), [k]: v } }))

  const run = async (s: Skill) => {
    const vals = open[s.name] || {}
    const coerced: Record<string, unknown> = {}
    for (const [k, t] of Object.entries(s.params)) {
      const raw = vals[k] ?? ''
      if (t === 'int') coerced[k] = raw === '' ? 0 : parseInt(raw, 10) || 0
      else if (t === 'bool') coerced[k] = raw === 'true' || raw === '1'
      else coerced[k] = raw
    }
    setRunning(s.name)
    setResult((prev) => ({ ...prev, [s.name]: '' }))
    try {
      const r = await api.runSkill(s.name, coerced)
      setResult((prev) => ({ ...prev, [s.name]: r.error ? `Error: ${r.error}` : String(r.result ?? '') }))
    } catch (e: any) {
      setResult((prev) => ({ ...prev, [s.name]: e?.message || 'Failed to run' }))
    } finally {
      setRunning(null)
    }
  }

  return (
    <div className="space-y-6 max-w-5xl">
      <div>
        <h2 className="text-xl font-semibold text-neutral-100">Skills</h2>
        <p className="text-sm text-neutral-500 mt-1">
          Executable agent skills — inspect parameters and run them locally.
        </p>
      </div>

      <div className="flex items-center gap-3 flex-wrap">
        <div className="grid grid-cols-2 gap-3">
          <div className="rounded-lg border border-neutral-800 bg-neutral-900/60 px-4 py-3">
            <div className="text-2xl font-semibold text-neutral-100">{skills.length}</div>
            <div className="text-[11px] uppercase tracking-wider text-neutral-500 mt-0.5">Skills</div>
          </div>
          <div className="rounded-lg border border-neutral-800 bg-neutral-900/60 px-4 py-3">
            <div className="text-2xl font-semibold text-amber-300">{nonDet}</div>
            <div className="text-[11px] uppercase tracking-wider text-neutral-500 mt-0.5">Non-deterministic</div>
          </div>
        </div>
        <div className="flex-1 min-w-48">
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Filter skills…"
            className="w-full px-3 py-2 rounded-lg bg-neutral-950 border border-neutral-800 text-sm text-neutral-200 placeholder:text-neutral-600 focus:outline-none focus:border-sky-500"
          />
        </div>
      </div>

      {err && <div className="text-sm text-red-400">{err}</div>}

      {visible.length === 0 ? (
        <div className="rounded-xl border border-dashed border-neutral-800 p-12 text-center">
          <p className="text-sm text-neutral-500">
            {skills.length === 0 ? 'No skills found.' : 'No skills match your filter.'}
          </p>
        </div>
      ) : (
        <div className="grid gap-3 md:grid-cols-2">
          {visible.map((s) => {
            const firstLine = s.description.split('\n')[0] || s.name
            const vals = open[s.name] || {}
            const pkeys = Object.keys(s.params)
            const out = result[s.name]
            const failed = out?.startsWith('Error:')
            return (
              <div key={s.name} className="rounded-xl border border-neutral-800 bg-neutral-900/60 p-4 flex flex-col">
                <div className="flex justify-between items-start gap-2 mb-1.5">
                  <div className="min-w-0">
                    <div className="font-mono text-sm font-semibold text-neutral-100 truncate">{s.name}</div>
                    <div className="text-xs text-neutral-500 mt-0.5 leading-relaxed">{firstLine}</div>
                  </div>
                  {s.non_deterministic && (
                    <span className="shrink-0 text-[10px] uppercase tracking-wider text-amber-300 bg-amber-500/10 ring-1 ring-amber-500/20 px-1.5 py-0.5 rounded">
                      non-det
                    </span>
                  )}
                </div>

                <div className="space-y-2.5 my-3 flex-1">
                  {pkeys.length === 0 ? (
                    <div className="text-xs text-neutral-600 italic">no parameters</div>
                  ) : (
                    pkeys.map((k) => (
                      <label key={k} className="block">
                        <div className="flex justify-between text-xs mb-1">
                          <span className="text-neutral-300 font-mono">{k}</span>
                          <span className="text-neutral-600">{s.params[k]}</span>
                        </div>
                        <input
                          value={vals[k] ?? ''}
                          onChange={(e) => update(s.name, k, e.target.value)}
                          placeholder={`--${k}`}
                          className="w-full px-2.5 py-1.5 rounded-lg bg-neutral-950 border border-neutral-800 text-sm text-neutral-200 font-mono placeholder:text-neutral-700 focus:outline-none focus:border-sky-500"
                        />
                      </label>
                    ))
                  )}
                </div>

                <button
                  onClick={() => run(s)}
                  disabled={running === s.name}
                  className="w-full text-sm px-3 py-2 rounded-lg bg-sky-600 hover:bg-sky-500 disabled:opacity-60 disabled:cursor-not-allowed text-white font-medium transition-colors"
                >
                  {running === s.name ? 'Running…' : `Run ${s.name}`}
                </button>

                {out !== undefined && (
                  <div className={`mt-3 rounded-lg border overflow-hidden ${
                    failed ? 'border-red-500/30' : 'border-neutral-800'
                  }`}>
                    <div className={`px-3 py-1.5 text-[10px] font-semibold uppercase tracking-wider border-b ${
                      failed ? 'bg-red-500/10 text-red-300 border-red-500/20' : 'bg-neutral-950 text-neutral-500 border-neutral-800'
                    }`}>
                      {failed ? 'Error' : 'Output'}
                    </div>
                    <pre className="p-3 bg-neutral-950 text-xs text-neutral-300 font-mono whitespace-pre-wrap break-all max-h-64 overflow-y-auto">
                      {out || '(empty output)'}
                    </pre>
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
