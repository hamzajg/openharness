import { useEffect, useState } from 'react'
import { api } from '../api'
import Markdown from '../components/Markdown'
import Maturity from '../components/Maturity'
import { Card, ErrorNote, cn } from '../components/ui'

const MATURITY = 'MATURITY'

const BLOCKS = [
  'MANIFEST',
  'PRINCIPLES',
  'EVOLUTION',
  'skill-system',
  'rag',
  'command-bridge',
  'env-probe',
  'repos',
  'serve',
]

function NavButton({
  active,
  onClick,
  children,
}: {
  active: boolean
  onClick: () => void
  children: React.ReactNode
}) {
  return (
    <button
      onClick={onClick}
      aria-current={active ? 'true' : undefined}
      className={cn(
        'whitespace-nowrap rounded-lg px-3 py-2 text-left text-sm transition-colors',
        active
          ? 'bg-sky-500/10 text-sky-200 ring-1 ring-inset ring-sky-500/20'
          : 'text-ink-dim hover:bg-surface/60 hover:text-ink',
      )}
    >
      {children}
    </button>
  )
}

export default function Self() {
  const [block, setBlock] = useState(MATURITY)
  const [text, setText] = useState('')
  const [err, setErr] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (block === MATURITY) {
      setText('')
      setLoading(false)
      return
    }
    setLoading(true)
    setErr(null)
    api
      .self(block === 'MANIFEST' ? undefined : block)
      .then((r) => setText(r.text))
      .catch((e) => setErr(e?.message || 'Failed to load block'))
      .finally(() => setLoading(false))
  }, [block])

  return (
    <div className="flex flex-col gap-6 lg:flex-row">
      <nav className="shrink-0 lg:sticky lg:top-24 lg:w-48 lg:self-start">
        <div className="hidden px-1 pb-2 text-[11px] font-semibold uppercase tracking-wider text-ink-faint lg:block">
          Harness
        </div>
        <div className="flex gap-0.5 overflow-x-auto pb-1 lg:flex-col lg:overflow-visible lg:pb-0">
          <NavButton active={block === MATURITY} onClick={() => setBlock(MATURITY)}>
            Maturity
            <span className="ml-1.5 text-[10px] text-sky-400/70">live</span>
          </NavButton>
          <div className="my-2 hidden border-t border-line lg:block" />
          <div className="hidden px-1 pb-1 text-[11px] font-semibold uppercase tracking-wider text-ink-faint lg:block">
            Spec blocks
          </div>
          {BLOCKS.map((b) => (
            <NavButton key={b} active={block === b} onClick={() => setBlock(b)}>
              {b}
            </NavButton>
          ))}
        </div>
      </nav>

      <div className="min-w-0 flex-1">
        {block === MATURITY ? (
          <Maturity />
        ) : (
          <article className="lg:max-w-3xl">
            {err ? (
              <ErrorNote>{err}</ErrorNote>
            ) : (
              <Card className="px-6 py-6 md:px-8 md:py-7">
                <header className="mb-2 flex items-center gap-2 border-b border-line pb-4">
                  <span className="font-mono text-[11px] font-semibold uppercase tracking-wider text-ink-mute">
                    {block}
                  </span>
                  {loading && <span className="text-[11px] text-ink-faint">loading…</span>}
                </header>
                <Markdown text={text} />
              </Card>
            )}
          </article>
        )}
      </div>
    </div>
  )
}
