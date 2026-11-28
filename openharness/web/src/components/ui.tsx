import {
  type ButtonHTMLAttributes,
  type InputHTMLAttributes,
  type ReactNode,
  createContext,
  useContext,
  useEffect,
  useId,
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
  info: 'bg-info/10 text-info ring-info/30',
  ok: 'bg-ok/10 text-ok ring-ok/30',
  warn: 'bg-warn/10 text-warn ring-warn/30',
  danger: 'bg-danger/10 text-danger ring-danger/30',
  alt: 'bg-alt/10 text-alt ring-alt/30',
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
        aria-hidden="true"
        className={cn(
          'h-1.5 w-1.5 rounded-full',
          live ? 'animate-pulse bg-ok' : 'bg-ink-faint',
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
    <code className="rounded bg-surface px-1.5 py-0.5 font-mono text-xs text-accent">
      {children}
    </code>
  )
}

/* -------------------------------------------------------- controls */

type ButtonVariant = 'primary' | 'secondary' | 'ghost'

const BUTTON_VARIANT: Record<ButtonVariant, string> = {
  primary: 'bg-accent-strong text-white hover:bg-accent-strong-hover',
  secondary: 'border border-line bg-surface text-ink-body hover:bg-line hover:text-ink',
  ghost: 'text-ink-dim hover:bg-surface hover:text-ink',
}

export function Button({
  variant = 'secondary',
  size = 'md',
  className,
  children,
  type = 'button',
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: ButtonVariant; size?: 'sm' | 'md' }) {
  return (
    <button
      type={type}
      className={cn(
        'inline-flex items-center justify-center gap-1.5 rounded-lg font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-60',
        size === 'sm' ? 'px-2.5 py-1.5 text-xs' : 'px-3 py-2 text-sm',
        BUTTON_VARIANT[variant],
        className,
      )}
      {...rest}
    >
      {children}
    </button>
  )
}

/* A Field wires its label, hint and error to the control it wraps, so
   every input is named and every error announced without boilerplate. */

interface FieldContextValue {
  id: string
  describedBy?: string
  invalid: boolean
}

const FieldContext = createContext<FieldContextValue | null>(null)

export function Field({
  label,
  hint,
  error,
  children,
}: {
  label: string
  hint?: ReactNode
  error?: ReactNode
  children: ReactNode
}) {
  const id = useId()
  const hintId = `${id}-hint`
  const errorId = `${id}-error`
  const describedBy =
    [hint ? hintId : null, error ? errorId : null].filter(Boolean).join(' ') || undefined

  return (
    <div className="block">
      <div className="mb-1 flex items-baseline justify-between gap-2">
        <label htmlFor={id} className="font-mono text-xs text-ink-body">
          {label}
        </label>
        {hint && (
          <span id={hintId} className="text-[11px] text-ink-faint">
            {hint}
          </span>
        )}
      </div>
      <FieldContext.Provider value={{ id, describedBy, invalid: Boolean(error) }}>
        {children}
      </FieldContext.Provider>
      {error && (
        <p id={errorId} role="alert" className="mt-1 text-[11px] text-danger">
          {error}
        </p>
      )}
    </div>
  )
}

export function Input({
  className,
  ...rest
}: InputHTMLAttributes<HTMLInputElement>) {
  const field = useContext(FieldContext)
  const {
    id,
    'aria-invalid': ariaInvalid,
    'aria-describedby': ariaDescribedBy,
    ...props
  } = rest
  const invalid = ariaInvalid ?? (field?.invalid ? true : undefined)

  return (
    <input
      id={id ?? field?.id}
      aria-invalid={invalid}
      aria-describedby={ariaDescribedBy ?? field?.describedBy}
      className={cn(
        'w-full rounded-lg border border-line bg-canvas px-3 py-2 text-sm text-ink placeholder:text-ink-faint',
        invalid
          ? 'border-danger/60 focus:border-danger focus:outline-none focus:ring-2 focus:ring-danger/20'
          : 'focus:border-accent/70 focus:outline-none focus:ring-2 focus:ring-accent/20',
        className,
      )}
      {...props}
    />
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
  label,
}: {
  value: T
  options: SegOption<T>[]
  onChange: (v: T) => void
  label?: string
}) {
  return (
    <div
      role="group"
      aria-label={label}
      className="inline-flex flex-wrap gap-1 rounded-lg border border-line bg-surface/60 p-1"
    >
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          onClick={() => onChange(o.value)}
          aria-pressed={value === o.value}
          className={cn(
            'rounded-md px-2.5 py-1.5 text-xs font-medium transition-colors',
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
        <div aria-hidden="true" className="mt-2 h-1 overflow-hidden rounded-full bg-line">
          <div
            className={cn('h-full rounded-full', bar.over ? 'bg-warn' : 'bg-ok')}
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
    <div
      role="alert"
      className="flex items-start gap-2 rounded-lg border border-danger/30 bg-danger/5 px-3 py-2 text-sm text-danger"
    >
      <IconAlert className="mt-0.5 h-4 w-4 shrink-0" />
      <span className="min-w-0">{children}</span>
    </div>
  )
}

export function Loading({ label = 'Loading…' }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 text-sm text-ink-mute" role="status">
      <span
        aria-hidden="true"
        className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-line border-t-accent"
      />
      {label}
    </div>
  )
}

export function OutputBlock({ text, error }: { text: string; error?: boolean }) {
  return (
    <div
      className={cn(
        'mt-3 overflow-hidden rounded-lg border',
        error ? 'border-danger/30' : 'border-line',
      )}
    >
      <div
        className={cn(
          'border-b px-3 py-1.5 text-[10px] font-semibold uppercase tracking-wider',
          error
            ? 'border-danger/20 bg-danger/10 text-danger'
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

const FOCUSABLE =
  'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])'

/**
 * Side pane over the current page.
 *
 * `modal` is opt-in: a side pane keeps the background readable and
 * usable, so it does not claim `aria-modal`, trap focus or lock body
 * scroll. A blocking dialog sets `modal` and gets all three.
 *
 * On open, focus moves to the pane (labelled by its heading); on close,
 * focus returns to the control that opened it.
 */
export function Drawer({
  open,
  onClose,
  title,
  subtitle,
  meta,
  headerExtra,
  accent,
  wide,
  modal = false,
  closeOnBackdrop,
  closeOnEscape = true,
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
  modal?: boolean
  closeOnBackdrop?: boolean
  closeOnEscape?: boolean
  children: ReactNode
}) {
  const panelRef = useRef<HTMLElement>(null)
  const returnFocus = useRef<HTMLElement | null>(null)
  const onCloseRef = useRef(onClose)
  onCloseRef.current = onClose
  const titleId = useId()
  const descId = useId()
  const backdropCloses = closeOnBackdrop ?? !modal

  useEffect(() => {
    if (!open) return
    returnFocus.current = (document.activeElement as HTMLElement | null) ?? null
    const panel = panelRef.current
    const previousOverflow = document.body.style.overflow
    if (modal) document.body.style.overflow = 'hidden'
    panel?.focus()

    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && closeOnEscape) {
        e.preventDefault()
        onCloseRef.current()
        return
      }
      if (!modal || e.key !== 'Tab' || !panel) return
      const nodes = Array.from(panel.querySelectorAll<HTMLElement>(FOCUSABLE)).filter(
        (el) => el.getClientRects().length > 0,
      )
      if (nodes.length === 0) {
        e.preventDefault()
        panel.focus()
        return
      }
      const first = nodes[0]
      const last = nodes[nodes.length - 1]
      if (e.shiftKey && (document.activeElement === first || document.activeElement === panel)) {
        e.preventDefault()
        last.focus()
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault()
        first.focus()
      }
    }

    window.addEventListener('keydown', onKey)
    return () => {
      window.removeEventListener('keydown', onKey)
      if (modal) document.body.style.overflow = previousOverflow
      returnFocus.current?.focus?.()
    }
    // onClose is read through a ref so an inline handler does not re-run
    // this effect (and steal focus back) on every parent render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, modal, closeOnEscape])

  if (!open) return null

  return (
    <div className="fixed inset-0 z-40">
      <div
        aria-hidden="true"
        onClick={backdropCloses ? () => onCloseRef.current() : undefined}
        className={cn(
          'drawer-backdrop absolute inset-0 bg-black/60 backdrop-blur-[2px]',
          backdropCloses && 'cursor-pointer',
        )}
      />
      <aside
        ref={panelRef}
        tabIndex={-1}
        role="dialog"
        aria-modal={modal || undefined}
        aria-labelledby={titleId}
        aria-describedby={subtitle ? descId : undefined}
        className={cn(
          'drawer-panel absolute inset-y-0 right-0 flex max-w-full flex-col border-l border-line bg-canvas shadow-2xl outline-none',
          wide ? 'w-full sm:w-[560px]' : 'w-full sm:w-[440px]',
        )}
      >
        <header className={cn('border-b border-line border-l-2 px-5 py-4', accent)}>
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <h2 id={titleId} className="truncate text-base font-semibold text-ink">
                {title}
              </h2>
              {subtitle && (
                <p id={descId} className="mt-0.5 truncate font-mono text-xs text-ink-mute">
                  {subtitle}
                </p>
              )}
            </div>
            <div className="flex shrink-0 items-center gap-2">
              {headerExtra}
              <button
                type="button"
                onClick={() => onCloseRef.current()}
                aria-label="Close panel"
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
        <div className="flex-1 overflow-y-auto overscroll-contain px-5 py-4">{children}</div>
      </aside>
    </div>
  )
}
