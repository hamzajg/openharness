import { useEffect, useState } from 'react'
import { api, Skill } from '../api'

export default function Skills() {
  const [skills, setSkills] = useState<Skill[]>([])
  const [err, setErr] = useState<string | null>(null)
  const [open, setOpen] = useState<Record<string, Record<string, string>>>({})
  const [running, setRunning] = useState<string | null>(null)
  const [result, setResult] = useState<Record<string, string>>({})

  useEffect(() => {
    api.skills().then(setSkills).catch((e) => setErr(e?.message || 'Failed to load skills'))
  }, [])

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
    <div>
      <h2 className="text-lg font-semibold mb-4">Skill Catalog</h2>
      {err && <div className="mb-3 text-sm text-red-400">{err}</div>}
      <div className="grid gap-3 md:grid-cols-2">
        {skills.map((s) => {
          const firstLine = s.description.split('\n')[0] || s.name
          const vals = open[s.name] || {}
          const pkeys = Object.keys(s.params)
          return (
            <div key={s.name} className="border border-neutral-800 rounded-lg p-4 bg-neutral-900/30">
              <div className="flex justify-between items-start mb-2">
                <div>
                  <div className="font-semibold text-neutral-100">{s.name}</div>
                  <div className="text-xs text-neutral-400 mt-0.5">{firstLine}</div>
                </div>
                {s.non_deterministic && (
                  <span className="text-[10px] uppercase tracking-wider text-amber-400 bg-amber-400/10 px-1.5 py-0.5 rounded">non-det</span>
                )}
              </div>
              <div className="space-y-2 my-3">
                {pkeys.length === 0 ? (
                  <div className="text-xs text-neutral-500 italic">no parameters</div>
                ) : (
                  pkeys.map((k) => (
                    <label key={k} className="block">
                      <div className="flex justify-between text-xs mb-1">
                        <span className="text-neutral-300">{k}</span>
                        <span className="text-neutral-500">{s.params[k]}</span>
                      </div>
                      <input
                        value={vals[k] ?? ''}
                        onChange={(e) => update(s.name, k, e.target.value)}
                        placeholder={`--${k}=value`}
                        className="w-full px-2 py-1.5 rounded bg-neutral-950 border border-neutral-700 text-sm text-neutral-200 focus:outline-none focus:border-neutral-500"
                      />
                    </label>
                  ))
                )}
              </div>
              <button
                onClick={() => run(s)}
                disabled={running === s.name}
                className="w-full text-sm px-3 py-1.5 rounded bg-emerald-600 hover:bg-emerald-500 disabled:opacity-60 disabled:cursor-not-allowed text-white"
              >
                {running === s.name ? 'Running…' : `Run ${s.name}`}
              </button>
              {result[s.name] !== undefined && (
                <pre className="mt-3 p-3 rounded bg-neutral-950 border border-neutral-800 text-xs text-neutral-300 whitespace-pre-wrap break-all max-h-64 overflow-y-auto">
                  {result[s.name] || '(empty output)'}
                </pre>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
