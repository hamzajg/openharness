import { useEffect, useMemo, useState } from 'react'
import { api, Skill } from '../api'
import {
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorNote,
  Field,
  Input,
  Loading,
  OutputBlock,
  Toolbar,
} from '../components/ui'
import { IconPlay } from '../components/icons'

interface RunResult {
  text: string
  error: boolean
}

export default function Skills() {
  const [skills, setSkills] = useState<Skill[]>([])
  const [err, setErr] = useState<string | null>(null)
  const [loaded, setLoaded] = useState(false)
  const [values, setValues] = useState<Record<string, Record<string, string>>>({})
  const [running, setRunning] = useState<string | null>(null)
  const [output, setOutput] = useState<Record<string, RunResult>>({})
  const [query, setQuery] = useState('')

  useEffect(() => {
    api
      .skills()
      .then(setSkills)
      .catch((e) => setErr(e?.message || 'Failed to load skills'))
      .finally(() => setLoaded(true))
  }, [])

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q) return skills
    return skills.filter(
      (s) => s.name.toLowerCase().includes(q) || s.description.toLowerCase().includes(q),
    )
  }, [skills, query])

  const nonDet = skills.filter((s) => s.non_deterministic).length

  const setValue = (name: string, key: string, value: string) =>
    setValues((prev) => ({ ...prev, [name]: { ...(prev[name] || {}), [key]: value } }))

  const run = async (s: Skill) => {
    const vals = values[s.name] || {}
    const coerced: Record<string, unknown> = {}
    for (const [key, type] of Object.entries(s.params)) {
      const raw = vals[key] ?? ''
      if (type === 'int') coerced[key] = raw === '' ? 0 : parseInt(raw, 10) || 0
      else if (type === 'bool') coerced[key] = raw === 'true' || raw === '1'
      else coerced[key] = raw
    }

    setRunning(s.name)
    setOutput((prev) => ({ ...prev, [s.name]: { text: '', error: false } }))
    try {
      const r = await api.runSkill(s.name, coerced)
      if (r.error) throw new Error(r.error)
      setOutput((prev) => ({ ...prev, [s.name]: { text: String(r.result ?? ''), error: false } }))
    } catch (e: any) {
      setOutput((prev) => ({
        ...prev,
        [s.name]: { text: e?.message || 'Failed to run', error: true },
      }))
    } finally {
      setRunning(null)
    }
  }

  if (!loaded) return <Loading />
  if (err && skills.length === 0) return <ErrorNote>{err}</ErrorNote>

  return (
    <div className="space-y-6">
      <Toolbar className="justify-between">
        <div className="w-full sm:max-w-xs">
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Filter skills…"
          />
        </div>
        <p className="text-xs text-ink-mute">
          {skills.length} skill{skills.length === 1 ? '' : 's'} ·{' '}
          <span className="text-warn">{nonDet}</span> non-deterministic
        </p>
      </Toolbar>

      {err && <ErrorNote>{err}</ErrorNote>}

      {visible.length === 0 ? (
        <EmptyState
          title={skills.length === 0 ? 'No skills found.' : 'No skills match your filter.'}
          action={
            skills.length > 0 ? (
              <Button variant="secondary" size="sm" onClick={() => setQuery('')}>
                Clear filter
              </Button>
            ) : undefined
          }
        />
      ) : (
        <div className="grid gap-3 md:grid-cols-2">
          {visible.map((s) => {
            const vals = values[s.name] || {}
            const paramKeys = Object.keys(s.params)
            const result = output[s.name]
            const firstLine = s.description.split('\n')[0] || s.name
            const isRunning = running === s.name

            return (
              <Card key={s.name} className="flex flex-col p-4">
                <div className="mb-1.5 flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <div className="truncate font-mono text-sm font-semibold text-ink">{s.name}</div>
                    <p className="mt-0.5 text-xs leading-relaxed text-ink-mute">{firstLine}</p>
                  </div>
                  {s.non_deterministic && <Badge tone="warn">non-det</Badge>}
                </div>

                <div className="my-3 flex-1 space-y-2.5">
                  {paramKeys.length === 0 ? (
                    <p className="text-xs italic text-ink-faint">no parameters</p>
                  ) : (
                    paramKeys.map((key) => (
                      <Field key={key} label={key} hint={s.params[key]}>
                        <Input
                          value={vals[key] ?? ''}
                          onChange={(e) => setValue(s.name, key, e.target.value)}
                          placeholder={`--${key}`}
                          className="py-1.5 font-mono text-xs"
                        />
                      </Field>
                    ))
                  )}
                </div>

                <Button
                  variant="primary"
                  onClick={() => run(s)}
                  disabled={isRunning}
                  className="w-full"
                >
                  <IconPlay className="h-3.5 w-3.5" />
                  {isRunning ? 'Running…' : 'Run'}
                </Button>

                {result && <OutputBlock text={result.text} error={result.error} />}
              </Card>
            )
          })}
        </div>
      )}
    </div>
  )
}
