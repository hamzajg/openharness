import { useEffect, useRef, useState } from 'react'
import { api, SessionMeta } from '../api'
import { fmtDateTime, relTime, useInterval } from '../lib/format'
import {
  Badge,
  Code,
  Drawer,
  EmptyState,
  ErrorNote,
  ListCard,
  LiveBadge,
  Loading,
  Toolbar,
  cn,
  type Tone,
} from '../components/ui'
import { IconChevronRight } from '../components/icons'

/* ------------------------------------------------ transcript lines */

interface LineView {
  role: string
  tone: Tone
  text: string
}

const ROLE_TONE: Record<string, Tone> = {
  assistant: 'info',
  user: 'neutral',
  system: 'alt',
  summary: 'alt',
  result: 'ok',
  tool: 'warn',
}

function summarize(input: unknown): string {
  if (input == null) return ''
  if (typeof input === 'string') return input.length > 120 ? `${input.slice(0, 120)}…` : input
  try {
    const s = JSON.stringify(input)
    return s.length > 120 ? `${s.slice(0, 120)}…` : s
  } catch {
    return ''
  }
}

/** Best-effort plain text out of a message `content` field (string or parts). */
function contentText(content: unknown): string {
  if (typeof content === 'string') return content
  if (!Array.isArray(content)) return ''
  const parts: string[] = []
  for (const part of content) {
    if (typeof part === 'string') {
      parts.push(part)
      continue
    }
    if (!part || typeof part !== 'object') continue
    const p = part as Record<string, any>
    if (typeof p.text === 'string' && p.text) {
      parts.push(p.text)
      continue
    }
    if (p.type === 'tool_use') {
      parts.push(`→ ${p.name ?? 'tool'} ${summarize(p.input)}`)
      continue
    }
    if (p.type === 'tool_result') {
      const nested = contentText(p.content)
      if (nested) parts.push(nested)
    }
  }
  return parts.join('\n').trim()
}

function compact(value: unknown): string {
  try {
    return JSON.stringify(value)
  } catch {
    return String(value)
  }
}

/** Turn an arbitrary agent log record into a readable line. */
function viewLine(line: unknown): LineView {
  if (line == null) return { role: 'empty', tone: 'neutral', text: '(empty line)' }
  if (typeof line === 'string') return { role: 'text', tone: 'neutral', text: line }
  if (typeof line !== 'object') return { role: 'value', tone: 'neutral', text: String(line) }
  const o = line as Record<string, any>
  if (typeof o._raw === 'string') return { role: 'raw', tone: 'neutral', text: o._raw }
  const msg = (o.message ?? {}) as Record<string, any>
  const role = String(msg.role ?? o.role ?? o.type ?? 'event')
  const text =
    contentText(msg.content ?? o.content) ||
    (typeof o.text === 'string' ? o.text : '') ||
    compact(o)
  return { role, tone: ROLE_TONE[role] ?? 'neutral', text }
}

function Transcript({ id }: { id: string }) {
  const [lines, setLines] = useState<unknown[]>([])
  const [error, setError] = useState<string | null>(null)
  const [ready, setReady] = useState(false)
  const boxRef = useRef<HTMLDivElement>(null)
  const stick = useRef(true)

  useEffect(() => {
    let cancelled = false
    let es: EventSource | null = null
    ;(async () => {
      try {
        const initial = await api.sessionLines(id)
        if (!cancelled) setLines(initial.lines)
      } catch (e: any) {
        if (!cancelled) setError(e?.message || 'Failed to load transcript')
        return
      } finally {
        if (!cancelled) setReady(true)
      }
      try {
        es = new EventSource(`/api/stream/${encodeURIComponent(id)}`)
        es.addEventListener('line', (ev: MessageEvent) => {
          try {
            const data = JSON.parse(ev.data)
            setLines((prev) => [...prev, data])
          } catch {}
        })
        es.onerror = () => setError('Stream interrupted — reopen the session to resume.')
      } catch (e: any) {
        setError(e?.message || 'Stream failed')
      }
    })()
    return () => {
      cancelled = true
      if (es) es.close()
    }
  }, [id])

  // Follow new output unless the reader scrolled up.
  useEffect(() => {
    const el = boxRef.current
    if (el && stick.current) el.scrollTop = el.scrollHeight
  }, [lines.length])

  if (error) return <ErrorNote>{error}</ErrorNote>
  if (!ready) return <Loading label="Loading transcript…" />
  if (lines.length === 0) return <p className="text-sm text-ink-mute">Transcript is empty.</p>

  return (
    <div
      ref={boxRef}
      onScroll={() => {
        const el = boxRef.current
        if (el) stick.current = el.scrollHeight - el.scrollTop - el.clientHeight < 48
      }}
      className="max-h-[70vh] space-y-1.5 overflow-y-auto pr-1"
    >
      {lines.map((line, i) => {
        const { role, tone, text } = viewLine(line)
        return (
          <div key={i} className="rounded-lg border border-line/70 bg-surface/40 px-3 py-2">
            <div className="mb-1 flex items-center justify-between gap-2">
              <Badge tone={tone} mono>
                {role}
              </Badge>
              <span className="font-mono text-[10px] text-ink-faint">#{i + 1}</span>
            </div>
            <p className="whitespace-pre-wrap break-words font-mono text-[11px] leading-relaxed text-ink-body">
              {text}
            </p>
          </div>
        )
      })}
    </div>
  )
}

/* ------------------------------------------------------------ rows */

function SessionRow({ s, onOpen }: { s: SessionMeta; onOpen: () => void }) {
  return (
    <button
      onClick={onOpen}
      className="group flex w-full items-center gap-3 px-4 py-3 text-left transition-colors hover:bg-surface/60"
    >
      <span
        className={cn(
          'h-2 w-2 shrink-0 rounded-full',
          s.active ? 'animate-pulse bg-emerald-500' : 'bg-ink-faint',
        )}
        title={s.active ? 'Active' : 'Idle'}
      />
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="text-sm text-ink">{s.agent}</span>
          <span className="truncate font-mono text-[11px] text-ink-faint" title={s.project_path}>
            {s.project_path}
          </span>
        </div>
        <p className="mt-0.5 truncate font-mono text-xs text-ink-dim">
          {s.current_command || 'no command yet'}
        </p>
      </div>
      <span className="shrink-0 text-xs text-ink-mute" title={fmtDateTime(s.last_seen)}>
        {relTime(s.last_seen)}
      </span>
      <IconChevronRight className="h-3.5 w-3.5 shrink-0 text-ink-faint transition-colors group-hover:text-ink-dim" />
    </button>
  )
}

/* ------------------------------------------------------------ page */

export default function Sessions() {
  const [data, setData] = useState<Record<string, SessionMeta[]>>({})
  const [err, setErr] = useState<string | null>(null)
  const [active, setActive] = useState<SessionMeta | null>(null)
  const [loaded, setLoaded] = useState(false)

  const load = async () => {
    try {
      setData(await api.sessions())
      setErr(null)
    } catch (e: any) {
      setErr(e?.message || 'Failed to load sessions')
    } finally {
      setLoaded(true)
    }
  }

  useEffect(() => {
    load()
  }, [])
  useInterval(load, 5000)

  const repos = Object.keys(data)
  const total = repos.reduce((n, r) => n + data[r].length, 0)

  if (!loaded) return <Loading />
  if (err && repos.length === 0) return <ErrorNote>{err}</ErrorNote>
  if (total === 0) {
    return (
      <EmptyState
        title="No agent sessions observed yet."
        action={
          <p className="max-w-md text-xs leading-relaxed text-ink-faint">
            Run <Code>oh serve</Code> in one terminal, then launch <Code>opencode</Code> or{' '}
            <Code>claude</Code> in another — sessions appear here automatically.
          </p>
        }
      />
    )
  }

  return (
    <div className="space-y-6">
      <Toolbar className="justify-between">
        <p className="text-xs text-ink-mute">
          {total} session{total === 1 ? '' : 's'} across {repos.length} project
          {repos.length === 1 ? '' : 's'}
        </p>
        <LiveBadge live label="auto-refresh 5s" />
      </Toolbar>

      {err && <ErrorNote>{err}</ErrorNote>}

      {repos.map((repo) => (
        <section key={repo} className="space-y-2">
          <div className="flex items-baseline gap-2">
            <h2 className="text-sm font-medium text-ink-body">
              {repo === 'external' ? 'External sessions' : `sources/${repo}`}
            </h2>
            <span className="text-xs text-ink-faint">{data[repo].length}</span>
          </div>
          <ListCard>
            {data[repo].map((s) => (
              <SessionRow key={s.id} s={s} onOpen={() => setActive(s)} />
            ))}
          </ListCard>
        </section>
      ))}

      <Drawer
        open={active !== null}
        onClose={() => setActive(null)}
        title={active ? `${active.agent} session` : ''}
        subtitle={active?.id}
        accent={active?.active ? 'border-l-emerald-500' : 'border-l-line'}
        wide
        headerExtra={
          active && (
            <Badge tone={active.active ? 'ok' : 'neutral'}>
              {active.active ? 'Active' : 'Idle'}
            </Badge>
          )
        }
        meta={active && <span>last seen {relTime(active.last_seen)}</span>}
      >
        {active && <Transcript id={active.id} />}
      </Drawer>
    </div>
  )
}
