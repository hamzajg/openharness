import { useEffect, useState } from 'react'
import { api } from '../api'
import Markdown from '../components/Markdown'
import Maturity from '../components/Maturity'

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

const MATURITY = 'MATURITY'

export default function Self() {
  const [block, setBlock] = useState<string>('MANIFEST')
  const [text, setText] = useState<string>('')
  const [err, setErr] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (block === MATURITY) {
      setText('')
      setLoading(false)
      return
    }
    const b = block === 'MANIFEST' ? undefined : block
    setLoading(true)
    api.self(b)
      .then((r) => setText(r.text))
      .catch((e) => setErr(e?.message || 'Failed to load'))
      .finally(() => setLoading(false))
  }, [block])

  const navItem = (id: string, label: string, accent = false) => {
    const active = block === id
    return (
      <button
        key={id}
        onClick={() => setBlock(id)}
        className={`px-3 py-2 rounded-lg text-left text-sm whitespace-nowrap transition-colors border-l-2 ${
          active
            ? 'border-sky-500 bg-neutral-800/70 text-neutral-100 font-medium'
            : 'border-transparent text-neutral-400 hover:text-neutral-200 hover:bg-neutral-800/40'
        }`}
      >
        {label}
        {accent && <span className="ml-1.5 text-[10px] text-sky-400/70">live</span>}
      </button>
    )
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold text-neutral-100">SELF</h2>
        <p className="text-sm text-neutral-500 mt-1">
          The harness's own spec — principles, decisions, and block contracts that govern agent behavior.
        </p>
      </div>

      {err && <div className="text-sm text-red-400">{err}</div>}

      <div className="flex flex-col lg:flex-row gap-6">
        {/* nav: maturity view first, then spec blocks */}
        <nav className="lg:w-48 shrink-0">
          <div className="text-[11px] font-semibold uppercase tracking-wider text-neutral-600 mb-2 px-1 hidden lg:block">
            Harness
          </div>
          <div className="flex lg:flex-col gap-0.5 overflow-x-auto lg:overflow-visible pb-1 lg:pb-0">
            {navItem(MATURITY, 'Maturity', true)}
            <div className="hidden lg:block border-t border-neutral-800 my-2 mx-1" />
            <div className="hidden lg:block text-[11px] font-semibold uppercase tracking-wider text-neutral-600 mb-1 px-1">
              Spec blocks
            </div>
            {BLOCKS.map((b) => navItem(b, b))}
          </div>
        </nav>

        {/* content */}
        {block === MATURITY ? (
          <div className="flex-1 min-w-0">
            <Maturity />
          </div>
        ) : (
          <article className="flex-1 min-w-0 lg:max-w-3xl">
            <div className="rounded-xl border border-neutral-800 bg-neutral-900/60 px-6 py-6 md:px-8 md:py-7">
              <header className="flex items-center gap-2 pb-4 mb-2 border-b border-neutral-800">
                <span className="text-[11px] font-semibold uppercase tracking-wider text-neutral-500 font-mono">
                  {block}
                </span>
                {loading && <span className="text-[11px] text-neutral-600">loading…</span>}
              </header>
              <Markdown text={text} />
            </div>
          </article>
        )}
      </div>
    </div>
  )
}
