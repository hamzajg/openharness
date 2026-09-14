import { Link, Route, Routes, useLocation } from 'react-router-dom'
import Sessions from './pages/Sessions'
import Skills from './pages/Skills'
import Self from './pages/Self'
import Knowledge from './pages/Knowledge'

export default function App() {
  const loc = useLocation()
  const nav = [
    { to: '/', label: 'Sessions' },
    { to: '/skills', label: 'Skills' },
    { to: '/self', label: 'SELF' },
    { to: '/knowledge', label: 'Knowledge' },
  ]
  return (
    <div className="min-h-full flex flex-col">
      <header className="border-b border-neutral-800 px-4 py-3 flex items-center gap-6">
        <h1 className="font-semibold tracking-tight text-sm text-neutral-200">
          OpenHarness <span className="text-neutral-500 text-xs ml-1">v0.1.0</span>
        </h1>
        <nav className="flex gap-1 text-sm">
          {nav.map((n) => {
            const active = (n.to === '/' ? loc.pathname === '/' : loc.pathname.startsWith(n.to))
            return (
              <Link
                key={n.to}
                to={n.to}
                className={`px-3 py-1.5 rounded-md transition-colors ${
                  active
                    ? 'bg-neutral-800 text-neutral-100'
                    : 'text-neutral-400 hover:text-neutral-200 hover:bg-neutral-800/50'
                }`}
              >
                {n.label}
              </Link>
            )
          })}
        </nav>
      </header>
      <main className="flex-1 p-4 md:p-6 overflow-y-auto">
        <Routes>
          <Route path="/" element={<Sessions />} />
          <Route path="/skills" element={<Skills />} />
          <Route path="/self" element={<Self />} />
          <Route path="/knowledge" element={<Knowledge />} />
        </Routes>
      </main>
    </div>
  )
}
