import type { Tone } from '../components/ui'

export interface StatusStyle {
  label: string
  tone: Tone
  /** Left accent border used by rows + drawer headers. */
  accent: string
}

const STATUS: Record<string, StatusStyle> = {
  running: { label: 'In progress', tone: 'info', accent: 'border-l-accent' },
  blocked: { label: 'Blocked', tone: 'warn', accent: 'border-l-warn' },
  done: { label: 'Done', tone: 'ok', accent: 'border-l-ok' },
}

export function loopStatus(status: string): StatusStyle {
  return (
    STATUS[status] ?? {
      label: status || 'Unknown',
      tone: 'neutral',
      accent: 'border-l-line',
    }
  )
}

export const WAVE_LABEL: Record<string, string> = {
  pending: 'Pending',
  'in-progress': 'In progress',
  done: 'Done',
}

export const GATE_LABEL: Record<string, string> = {
  pending: 'Pending',
  met: 'Met',
  waived: 'Waived',
  failed: 'Failed',
}

export function waveDotClass(status: string) {
  if (status === 'done') return 'bg-ok'
  if (status === 'in-progress') return 'animate-pulse bg-accent'
  return 'bg-line-strong'
}

export function gateTone(status: string) {
  if (status === 'met') return 'text-ok'
  if (status === 'waived') return 'text-alt'
  if (status === 'failed') return 'text-danger'
  return 'text-ink-dim'
}

/** "2026-…Z complete wave 2 (#8): evidence…" → readable {ts, text}. */
export function humanizeEvent(raw: string): { ts: string; text: string } {
  const m = raw.match(/^(\S+)\s+(.*)$/)
  const ts = m?.[1] ?? ''
  let text = m?.[2] ?? raw
  const sub = (re: RegExp, fn: (...a: string[]) => string) => {
    const mm = text.match(re)
    if (mm) text = fn(...mm.slice(1))
  }
  sub(/start wave (\d+) on (\S+)/, (w, b) => `Started wave ${w} on ${b}`)
  sub(
    /complete wave (\d+) \((#\d+)\):?\s*(.*)/,
    (w, pr, ev) => `Completed wave ${w} (${pr})${ev ? ` — ${ev}` : ''}`,
  )
  sub(/^blocked:\s*(G\d+):\s*(.*)/, (g, why) => `Blocked — ${g}: ${why}`)
  sub(/^blocked:\s*(.*)/, (why) => `Blocked — ${why}`)
  sub(/^feature validated and shipped/, () => 'Feature validated and shipped')
  sub(/^feature done/, () => 'Feature done')
  return { ts, text }
}

/** Pull the blocking reason out of the last event for the attention banner. */
export function blockReason(loop: { status: string; last_event: string }): string | null {
  if (loop.status !== 'blocked' || !loop.last_event) return null
  const { text } = humanizeEvent(loop.last_event)
  const m = text.match(/^Blocked\s*[—-]\s*(.*)/)
  return m ? m[1] : text
}
