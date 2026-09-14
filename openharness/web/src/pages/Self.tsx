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

  useEffect(() => {
    const b = block === 'MANIFEST' ? undefined : block
    api.self(b).then((r) => setText(r.text)).catch((e) => setErr(e?.message || 'Failed to load'))
  }, [block])

  return (
    <div>
      <div className="flex flex-wrap items-center gap-2 mb-4">
        <h2 className="text-lg font-semibold mr-3">SELF / Block Specs</h2>
        {BLOCKS.map((b) => (
          <button
            key={b}
            onClick={() => setBlock(b)}
            className={`text-xs px-2.5 py-1 rounded border ${
              block === b
                ? 'bg-neutral-800 border-neutral-600 text-neutral-100'
                : 'border-neutral-800 text-neutral-400 hover:text-neutral-200 hover:bg-neutral-800/50'
            }`}
          >
            {b}
          </button>
        ))}
      </div>
      {err && <div className="mb-3 text-sm text-red-400">{err}</div>}
      <div className="border border-neutral-800 rounded-lg p-5 bg-neutral-900/40">
        <Markdown text={text} />
      </div>
    </div>
  )
}
