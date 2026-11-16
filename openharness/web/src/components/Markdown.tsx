import { Children, cloneElement, isValidElement, useState, type ReactNode } from 'react'
import ReactMarkdown from 'react-markdown'

/* ---------- text extraction (hast -> plain text) ---------- */

function textOf(node: any): string {
  if (!node) return ''
  if (node.type === 'text') return node.value ?? ''
  if (Array.isArray(node.children)) return node.children.map(textOf).join('')
  return ''
}

/* ---------- GitHub-style alerts: > [!NOTE] / [!TIP] / [!IMPORTANT] / [!WARNING] / [!CAUTION] ---------- */

const ALERT_MARKER = /^\[alert-(\w+)\]\s*/

const ALERTS: Record<string, { label: string; text: string; box: string }> = {
  note:      { label: 'Note',      text: 'text-sky-300',     box: 'border-sky-500/30 bg-sky-500/5' },
  tip:       { label: 'Tip',       text: 'text-emerald-300', box: 'border-emerald-500/30 bg-emerald-500/5' },
  important: { label: 'Important', text: 'text-violet-300',  box: 'border-violet-500/30 bg-violet-500/5' },
  warning:   { label: 'Warning',   text: 'text-amber-300',   box: 'border-amber-500/30 bg-amber-500/5' },
  caution:   { label: 'Caution',   text: 'text-red-300',     box: 'border-red-500/30 bg-red-500/5' },
}

/** Strip the first [alert-x] marker from rendered children (it sits at the start of the first text node). */
function stripAlertMarker(children: ReactNode, done: { v: boolean }): ReactNode {
  return Children.map(children, (child) => {
    if (done.v || child == null || typeof child === 'boolean') return child
    if (typeof child === 'string') {
      if (ALERT_MARKER.test(child)) {
        done.v = true
        return child.replace(ALERT_MARKER, '')
      }
      return child
    }
    if (isValidElement(child)) {
      return cloneElement(child, {}, stripAlertMarker((child.props as any).children, done))
    }
    return child
  })
}

function AlertIcon({ kind }: { kind: string }) {
  if (kind === 'warning' || kind === 'caution') {
    return (
      <svg className="w-4 h-4 shrink-0 mt-0.5" viewBox="0 0 16 16" fill="currentColor">
        <path d="M6.457 1.047c.659-1.234 2.427-1.234 3.086 0l5.74 10.704A1.75 1.75 0 0113.74 14H2.26a1.75 1.75 0 01-1.543-2.249L6.457 1.047zM8 4.75a.75.75 0 01.75.75v3a.75.75 0 01-1.5 0V5.5A.75.75 0 018 4.75zM8 11a1 1 0 100-2 1 1 0 000 2z" />
      </svg>
    )
  }
  return (
    <svg className="w-4 h-4 shrink-0 mt-0.5" viewBox="0 0 16 16" fill="currentColor">
      <path d="M8 1.5a6.5 6.5 0 100 13 6.5 6.5 0 000-13zM0 8a8 8 0 1116 0A8 8 0 010 8zm9-3a1 1 0 10-2 0v3a1 1 0 001 1h1a1 1 0 100-2H9V5z" />
    </svg>
  )
}

/* ---------- code block with language label + copy ---------- */

function CodeBlock({ lang, code }: { lang: string; code: string }) {
  const [copied, setCopied] = useState(false)
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(code)
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch {}
  }
  return (
    <div className="rounded-lg border border-line bg-canvas overflow-hidden my-4">
      <div className="flex items-center justify-between px-3 py-1.5 border-b border-line/70 bg-surface/60">
        <span className="text-[10px] font-mono uppercase tracking-wider text-ink-mute">
          {lang || 'code'}
        </span>
        <button
          onClick={copy}
          className="text-[10px] font-medium text-ink-mute hover:text-ink transition-colors"
        >
          {copied ? 'Copied' : 'Copy'}
        </button>
      </div>
      <pre className="p-3.5 overflow-x-auto text-[13px] leading-6 font-mono text-ink-body">
        {code}
      </pre>
    </div>
  )
}

/* ---------- component overrides ---------- */

const components = {
  h1: ({ children, ...p }: any) => (
    <h1 className="text-xl font-bold text-ink border-b border-line pb-2 mt-2 mb-4" {...p}>
      {children}
    </h1>
  ),
  h2: ({ children, ...p }: any) => (
    <h2 className="text-base font-semibold text-ink border-b border-line/70 pb-1.5 mt-6 mb-3" {...p}>
      {children}
    </h2>
  ),
  h3: ({ children, ...p }: any) => (
    <h3 className="text-sm font-semibold text-ink mt-5 mb-2" {...p}>{children}</h3>
  ),
  h4: ({ children, ...p }: any) => (
    <h4 className="text-sm font-medium text-ink-body mt-4 mb-1.5" {...p}>{children}</h4>
  ),
  p: ({ children, ...p }: any) => (
    <p className="leading-7 text-ink-body my-3" {...p}>{children}</p>
  ),
  ul: ({ children, ...p }: any) => (
    <ul className="list-disc pl-5 space-y-1.5 marker:text-ink-faint my-3" {...p}>{children}</ul>
  ),
  ol: ({ children, ...p }: any) => (
    <ol className="list-decimal pl-5 space-y-1.5 marker:text-ink-faint my-3" {...p}>{children}</ol>
  ),
  li: ({ children, ...p }: any) => (
    <li className="leading-6 text-ink-body" {...p}>{children}</li>
  ),
  strong: ({ children, ...p }: any) => (
    <strong className="text-ink font-semibold" {...p}>{children}</strong>
  ),
  em: ({ children, ...p }: any) => (
    <em className="text-ink" {...p}>{children}</em>
  ),
  a: ({ children, ...p }: any) => (
    <a className="text-sky-400 hover:text-sky-300 underline underline-offset-2" target="_blank" rel="noreferrer" {...p}>
      {children}
    </a>
  ),
  hr: (p: any) => <hr className="border-line my-6" {...p} />,
  // inline code only — fenced blocks are handled by `pre` below
  code: ({ children, ...p }: any) => (
    <code className="rounded bg-surface px-1.5 py-0.5 font-mono text-[13px] text-sky-300" {...p}>
      {children}
    </code>
  ),
  pre: ({ node, children: _ignored, ...p }: any) => {
    const codeEl = (node?.children ?? []).find((c: any) => c.tagName === 'code')
    const cls = codeEl?.properties?.className ?? []
    const lang = (Array.isArray(cls) ? cls : []).find((c: string) => c.startsWith('language-'))?.slice(9) ?? ''
    const code = textOf(codeEl ?? node)
    return <CodeBlock lang={lang} code={code} {...p} />
  },
  blockquote: ({ node, children, ...p }: any) => {
    const t = textOf(node)
    const m = t.match(ALERT_MARKER)
    if (m) {
      const kind = m[1].toLowerCase()
      const a = ALERTS[kind] ?? ALERTS.note
      const done = { v: false }
      return (
        <div className={`rounded-lg border ${a.box} px-4 py-3 my-4`} {...p}>
          <div className={`flex items-center gap-1.5 mb-1 ${a.text}`}>
            <AlertIcon kind={kind} />
            <span className="text-[11px] font-semibold uppercase tracking-wider">{a.label}</span>
          </div>
          <div>{stripAlertMarker(children, done)}</div>
        </div>
      )
    }
    return (
      <blockquote className="border-l-2 border-line-strong pl-4 text-ink-dim my-4" {...p}>
        {children}
      </blockquote>
    )
  },
  table: ({ children, ...p }: any) => (
    <div className="overflow-x-auto rounded-lg border border-line my-4">
      <table className="w-full text-sm" {...p}>{children}</table>
    </div>
  ),
  th: ({ children, ...p }: any) => (
    <th className="px-3 py-2 text-left text-[11px] font-semibold uppercase tracking-wider text-ink-dim bg-surface/70 border-b border-line whitespace-nowrap" {...p}>
      {children}
    </th>
  ),
  td: ({ children, ...p }: any) => (
    <td className="px-3 py-2 border-b border-line/60 text-ink-body align-top" {...p}>
      {children}
    </td>
  ),
  img: ({ src, alt, ...p }: any) => (
    // eslint-disable-next-line @next/next/no-img-element
    <img src={src} alt={alt ?? ''} className="rounded-lg border border-line my-4 max-w-full" {...p} />
  ),
}

/** Normalize GitHub alert markers `> [!NOTE]` into `[alert-note]` for the blockquote renderer. */
function preprocess(text: string): string {
  return text
    .replace(/^---[ \t]*\r?\n[\s\S]*?\r?\n---[ \t]*\r?\n?/, '') // YAML frontmatter
    .replace(/^>\s*\[!(NOTE|TIP|IMPORTANT|WARNING|CAUTION)\][ \t]*$/gim, (_m, k) => `> [alert-${String(k).toLowerCase()}]`)
}

export default function Markdown({ text }: { text: string }) {
  return (
    <div className="text-[15px] leading-7 text-ink-body [&>:first-child]:mt-0 [&>:last-child]:mb-0">
      <ReactMarkdown components={components}>{preprocess(text)}</ReactMarkdown>
    </div>
  )
}
