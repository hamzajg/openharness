import { useEffect, useRef } from 'react'

/** Accepts epoch seconds, epoch millis, or an ISO string. */
export function toMs(input?: number | string | null): number | null {
  if (input == null || input === '') return null
  if (typeof input === 'number') return input < 1e12 ? input * 1000 : input
  const t = Date.parse(input)
  return Number.isNaN(t) ? null : t
}

export function relTime(input?: number | string | null): string {
  const ms = toMs(input)
  if (ms == null) return '—'
  const s = Math.max(0, Math.floor((Date.now() - ms) / 1000))
  if (s < 60) return `${s}s ago`
  if (s < 3600) return `${Math.floor(s / 60)}m ago`
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`
  return `${Math.floor(s / 86400)}d ago`
}

export function fmtDateTime(input?: number | string | null): string {
  const ms = toMs(input)
  if (ms == null) return '—'
  return new Date(ms).toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function fmtDate(input?: number | string | null): string {
  const ms = toMs(input)
  if (ms == null) return ''
  return new Date(ms).toLocaleDateString(undefined, {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  })
}

export function dayKey(input?: number | string | null): string {
  const ms = toMs(input)
  return ms == null ? String(input ?? '') : new Date(ms).toDateString()
}

/** setInterval with a stable timer — the callback may change every render. */
export function useInterval(cb: () => void, ms: number) {
  const ref = useRef(cb)
  ref.current = cb
  useEffect(() => {
    const id = setInterval(() => ref.current(), ms)
    return () => clearInterval(id)
  }, [ms])
}
