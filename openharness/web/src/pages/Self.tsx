import { useEffect, useState } from 'react'
import { api } from '../api'
import Markdown from '../components/Markdown'

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

export default function Self() {
  const [block, setBlock] = useState<string>('MANIFEST')
  const [text, setText] = useState<string>('')
  const [err, setErr] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    const b = block === 'MANIFEST' ? undefined : block
    setLoading(true)
    api.self(b)
      .then((r) => setText(r.text))
      .catch((e) => setErr(e?.message || 'Failed to load'))
      .finally(() => setLoading(false))
  }, [block])

  return (
    <div className="space-y-6 max-w-5xl">
      <div>
        <h2 className="text-xl font-semibold text-neutral-100">SELF</h2>
        <p className="text-sm text-neutral-500 mt-1">
          The harness's own spec — principles, decisions, and block contracts that govern agent behavior.
        </p>
      </div>

      {err && <div className="text-sm text-red-400">{err}</div>}

      <div className="flex flex-col lg:flex-row gap-5">
        {/* block nav: horizontal scroll on mobile, vertical rail on lg */}
        <nav className="lg:w-44 shrink-0">
          <div className="flex lg:flex-col gap-1 overflow-x-auto lg:overflow-visible pb-1 lg:pb-0">
            {BLOCKS.map((b) => (
              <button
                key={b}
                onClick={() => setBlock(b)}
                className={`px-3 py-2 rounded-lg text-left text-sm whitespace-nowrap transition-colors ${
                  block === b
                    ? 'bg-neutral-800 text-neutral-100 font-medium'
                    : 'text-neutral-400 hover:text-neutral-200 hover:bg-neutral-800/50'
                }`}
              >
                {b}
              </button>
            ))}
          </div>
        </nav>

        {/* content */}
        <div className="flex-1 min-w-0 rounded-xl border border-neutral-800 bg-neutral-900/60 p-5">
          <div className="flex items-center gap-2 mb-3 pb-3 border-b border-neutral-800">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-neutral-500">
              {block}
            </span>
            {loading && <span className="text-[11px] text-neutral-600">loading…</span>}
          </div>
          <Markdown text={text} />
        </div>
      </div>
    </div>
  )
}
