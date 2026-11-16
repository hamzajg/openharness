import {
  type ButtonHTMLAttributes,
  type InputHTMLAttributes,
  type ReactNode,
  useEffect,
  useRef,
} from 'react'
import { IconAlert, IconClose } from './icons'

export function cn(...parts: Array<string | false | null | undefined>) {
  return parts.filter(Boolean).join(' ')
}

/* ----------------------------------------------------------- tones */

export type Tone = 'neutral' | 'info' | 'ok' | 'warn' | 'danger' | 'alt'

const TONE_PILL: Record<Tone, string> = {
  neutral: 'bg-white/5 text-ink-dim ring-white/10',
  info: 'bg-sky-500/10 text-sky-300 ring-sky-500/30',
  ok: 'bg-emerald-500/10 text-emerald-300 ring-emerald-500/30',
  warn: 'bg-amber-500/10 text-amber-300 ring-amber-500/30',
  danger: 'bg-red-500/10 text-red-300 ring-red-500/30',
  alt: 'bg-violet-500/10 text-violet-300 ring-violet-500/30',
}

export function Badge({
  tone = 'neutral',
  mono,
  className,
  children,
}: {
  tone?: Tone
  mono?: boolean
  className?: string
  children: ReactNode
}) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 whitespace-nowrap rounded-full px-2 py-0.5 text-[11px] font-medium ring-1',
        TONE_PILL[tone],
        mono && 'font-mono',
        className,
      )}
    >
      {children}
    </span>
  )
}

export function LiveBadge({ live = true, label }: { live?: boolean; label?: string }) {
  return (
    <Badge tone={live ? 'ok' : 'neutral'}>
      <span
        className={cn(
          'h-1.5 w-1.5 rounded-full',
          live ? 'animate-pulse bg-emerald-400' : 'bg-ink-faint',
        )}
      />
      {label ?? (live ? 'Live' : 'Offline')}
    </Badge>
  )
}

/* -------------------------------------------------------- surfaces */

export function Card({ className, children }: { className?: string; children: ReactNode }) {
  return (
    <div className={cn('overflow-hidden rounded-xl border border-line bg-surface/60', className)}>
      {children}
    </div>
  )
}

/** Card pre-configured as a divided list of rows. */
export function ListCard({ className, children }: { className?: string; children: ReactNode }) {
  return <Card className={cn('divide-y divide-line/70', className)}>{children}</Card>
}

export function SectionTitle({ children, count }: { children: ReactNode; count?: number }) {
  return (
    <h3 className="mb-2.5 text-xs font-semibold uppercase tracking-wider text-ink-mute">
      {children}
      {count !== undefined && (
        <span className="ml-1.5 font-normal text-ink-faint">{count}</span>
      )}
    </h3>
  )
}

export function Toolbar({ className, children }: { className?: string; children: ReactNode }) {
  return (
    <div className={cn('flex flex-wrap items-center gap-3', className)}>{children}</div>
  )
}

export function Code({ children }: { children: ReactNode }) {
  return (
    <code className="rounded bg-surface px-1.5 py-0.5 font-mono text-xs text-sky-300">
      {children}
    </code>
  )
}

/* -------------------------------------------------------- controls */

type ButtonVariant = 'primary' | 'secondary' | 'ghost'

const BUTTON_VARIANT: Record<ButtonVariant, string> = {
  primary: 'bg-sky-600 text-white hover:bg-sky-500',
  secondary: 'border border-line bg-surface text-ink-body hover:bg-line hover:text-ink',
  ghost: 'text-ink-dim hover:bg-surface hover:text-ink',
}

export function Button({
  variant = 'secondary',
  size = 'md',
  className,
  children,
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: ButtonVariant; size?: 'sm' | 'md' }) {
  return (
    <button
      className={cn(
        'inline-flex items-center justify-center gap-1.5 rounded-lg font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-60',
        size === 'sm' ? 'px-2.5 py-1 text-xs' : 'px-3 py-2 text-sm',
        BUTTON_VARIANT[variant],
        className,
      )}
      {...rest}
    >
      {children}
    </button>
  )
}

export function Input({ className, ...rest }: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      className={cn(
        'w-full rounded-lg border border-line bg-canvas px-3 py-2 text-sm text-ink placeholder:text-ink-faint',
        'focus:border-sky-500/70 focus:outline-none focus:ring-2 focus:ring-sky-500/20',
        className,
      )}
      {...rest}
    />
  )
}

export function Field({
  label,
  hint,
  children,
}: {
  label: string
  hint?: ReactNode
  children: ReactNode
}) {
  return (
    <label className="block">
      <div className="mb-1 flex items-baseline justify-between gap-2">
        <span className="font-mono text-xs text-ink-body">{label}</span>
        {hint && <span className="text-[11px] text-ink-faint">{hint}</span>}
      </div>
      {children}
    </label>
  )
}

export interface SegOption<T extends string> {
  value: T
  label: string
  count?: number
}

export function SegmentedControl<T extends string>({
  value,
  options,
  onChange,
}: {
  value: T
  options: SegOption<T>[]
  onChange: (v: T) => void
}) {
  return (
    <div className="inline-flex flex-wrap gap-1 rounded-lg border border-line bg-surface/60 p-1">
      {options.map((o) => (
        <button
          key={o.value}
          onClick={() => onChange(o.value)}
          aria-pressed={value === o.value}
          className={cn(
            'rounded-md px-2.5 py-1 text-xs font-medium transition-colors',
            value === o.value ? 'bg-line text-ink' : 'text-ink-mute hover:text-ink-body',
          )}
        >
          {o.label}
          {o.count !== undefined && (
            <span className="ml-1.5 font-mono text-ink-faint">{o.count}</span>
          )}
        </button>
      ))}
    </div>
  )
}

/* ------------------------------------------------------------ stats */

export function StatCard({
  label,
  value,
  sub,
  tone = 'text-ink',
  bar,
}: {
  label: string
  value: ReactNode
  sub?: ReactNode
  tone?: string
  bar?: { pct: number; over?: boolean }
}) {
  return (
    <Card className="px-4 py-3">
      <div className={cn('text-xl font-semibold', tone)}>{value}</div>
      <div className="mt-0.5 text-[11px] uppercase tracking-wider text-ink-mute">{label}</div>
      {sub && <div className="mt-1 text-[11px] text-ink-faint">{sub}</div>}
      {bar && (
        <div className="mt-2 h-1 overflow-hidden rounded-full bg-line">
          <div
            className={cn('h-full rounded-full', bar.over ? 'bg-amber-500' : 'bg-emerald-500')}
            style={{ width: `${Math.min(100, bar.pct)}%` }}
          />
        </div>
      )}
    </Card>
  )
}

/* ---------------------------------------------------- states/output */

export function EmptyState({
  title,
  hint,
  action,
}: {
  title: ReactNode
  hint?: ReactNode
  action?: ReactNode
}) {
  return (
    <div className="rounded-xl border border-dashed border-line px-6 py-12 text-center">
      <p className="text-sm text-ink-mute">{title}</p>
      {hint && <p className="mt-1.5 font-mono text-xs text-ink-faint">{hint}</p>}
      {action && <div className="mt-4 flex justify-center">{action}</div>}
    </div>
  )
}

export function ErrorNote({ children }: { children: ReactNode }) {
  return (
    <div className="flex items-start gap-2 rounded-lg border border-red-500/30 bg-red-500/5 px-3 py-2 text-sm text-red-300">
      <IconAlert className="mt-0.5 h-4 w-4 shrink-0" />
      <span className="min-w-0">{children}</span>
    </div>
  )
}

export function Loading({ label = 'Loading…' }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 text-sm text-ink-mute">
      <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-line border-t-sky-400" />
      {label}
    </div>
  )
}

export function OutputBlock({ text, error }: { text: string; error?: boolean }) {
  return (
    <div
      className={cn(
        'mt-3 overflow-hidden rounded-lg border',
        error ? 'border-red-500/30' : 'border-line',
      )}
    >
      <div
        className={cn(
          'border-b px-3 py-1.5 text-[10px] font-semibold uppercase tracking-wider',
          error
            ? 'border-red-500/20 bg-red-500/10 text-red-300'
            : 'border-line bg-canvas text-ink-mute',
        )}
      >
        {error ? 'Error' : 'Output'}
      </div>
      <pre className="max-h-64 overflow-y-auto whitespace-pre-wrap break-all bg-canvas p-3 font-mono text-xs text-ink-body">
        {text || '(empty output)'}
      </pre>
    </div>
  )
}

/* ----------------------------------------------------------- drawer */

export function Drawer({
  open,
  onClose,
  title,
  subtitle,
  meta,
  headerExtra,
  accent,
  wide,
  children,
}: {
  open: boolean
  onClose: () => void
  title: ReactNode
  subtitle?: ReactNode
  meta?: ReactNode
  headerExtra?: ReactNode
  accent?: string
  wide?: boolean
  children: ReactNode
}) {
  const panelRef = useRef<HTMLElement>(null)

  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    const previous = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    panelRef.current?.focus()
    return () => {
      window.removeEventListener('keydown', onKey)
      document.body.style.overflow = previous
    }
  }, [open, onClose])

  if (!open) return null

  return (
    <div className="fixed inset-0 z-40" role="dialog" aria-modal="true">
      <button
        aria-label="Close"
        onClick={onClose}
        className="drawer-backdrop absolute inset-0 bg-black/60 backdrop-blur-[2px]"
      />
      <aside
        ref={panelRef}
        tabIndex={-1}
        className={cn(
          'drawer-panel absolute inset-y-0 right-0 flex w-full flex-col border-l border-line bg-canvas shadow-2xl outline-none',
          wide ? 'sm:w-[560px] lg:w-[680px]' : 'sm:w-[520px]',
        )}
      >
        <header className={cn('border-b border-line border-l-2 px-5 py-4', accent)}>
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <h2 className="truncate text-base font-semibold text-ink">{title}</h2>
              {subtitle && (
                <p className="mt-0.5 truncate font-mono text-xs text-ink-mute">{subtitle}</p>
              )}
            </div>
            <div className="flex shrink-0 items-center gap-2">
              {headerExtra}
              <button
                onClick={onClose}
                aria-label="Close"
                className="rounded-md p-1.5 text-ink-mute transition-colors hover:bg-surface hover:text-ink"
              >
                <IconClose className="h-4 w-4" />
              </button>
            </div>
          </div>
          {meta && (
            <div className="mt-2.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-ink-mute">
              {meta}
            </div>
          )}
        </header>
        <div className="flex-1 overflow-y-auto px-5 py-4">{children}</div>
      </aside>
    </div>
  )
}
