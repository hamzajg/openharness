import { Link, Route, Routes, useLocation } from 'react-router-dom'
import type { ComponentType } from 'react'
import Sessions from './pages/Sessions'
import Loops from './pages/Loops'
import Skills from './pages/Skills'
import Self from './pages/Self'
import Knowledge from './pages/Knowledge'
import { IconKnowledge, IconLoops, IconSelf, IconSessions, IconSkills, type IconProps } from './components/icons'
import { cn } from './components/ui'

interface NavItem {
  to: string
  label: string
  title: string
  description: string
  Icon: ComponentType<IconProps>
  end?: boolean
}

/** Single source of truth for the nav and the page headers. */
const NAV: NavItem[] = [
  {
    to: '/',
    label: 'Sessions',
    title: 'Sessions',
    description: 'Agent CLI sessions observed on this machine — read-only.',
    Icon: IconSessions,
    end: true,
  },
  {
    to: '/loops',
    label: 'Loops',
    title: 'Delivery Loops',
    description: 'Autonomous feature delivery across your repos — waves, gates, and history in real time.',
    Icon: IconLoops,
  },
  {
    to: '/skills',
    label: 'Skills',
    title: 'Skills',
    description: 'Executable agent skills — inspect parameters and run them locally.',
    Icon: IconSkills,
  },
  {
    to: '/self',
    label: 'SELF',
    title: 'SELF',
    description: "The harness's own spec — principles, decisions, and block contracts.",
    Icon: IconSelf,
  },
  {
    to: '/knowledge',
    label: 'Knowledge',
    title: 'Knowledge',
    description: 'Local RAG over ingested docs — semantic search, fully on-device.',
    Icon: IconKnowledge,
  },
]

function useActiveItem() {
  const { pathname } = useLocation()
  return (
    NAV.find((n) => (n.end ? pathname === n.to : pathname.startsWith(n.to))) ?? NAV[0]
  )
}

function Brand({ className }: { className?: string }) {
  return (
    <Link to="/" className={cn('flex items-center gap-2.5', className)}>
      <span className="grid h-7 w-7 shrink-0 place-items-center rounded-lg bg-sky-500/15 ring-1 ring-sky-500/30">
        <IconLoops className="h-4 w-4 text-sky-400" />
      </span>
      <span className="min-w-0">
        <span className="block text-sm font-semibold tracking-tight text-ink">OpenHarness</span>
        <span className="block text-[10px] uppercase tracking-wider text-ink-faint">
          observer · v0.1.0
        </span>
      </span>
    </Link>
  )
}

function SidebarLink({ item, active }: { item: NavItem; active: boolean }) {
  return (
    <Link
      to={item.to}
      aria-current={active ? 'page' : undefined}
      className={cn(
        'group flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm transition-colors',
        active
          ? 'bg-sky-500/10 text-sky-200 ring-1 ring-inset ring-sky-500/20'
          : 'text-ink-dim hover:bg-surface/60 hover:text-ink',
      )}
    >
      <item.Icon
        className={cn(
          'h-4 w-4 shrink-0',
          active ? 'text-sky-400' : 'text-ink-faint group-hover:text-ink-dim',
        )}
      />
      {item.label}
    </Link>
  )
}

function MobileNavLink({ item, active }: { item: NavItem; active: boolean }) {
  return (
    <Link
      to={item.to}
      aria-current={active ? 'page' : undefined}
      className={cn(
        'flex shrink-0 items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-colors',
        active ? 'bg-sky-500/10 text-sky-200' : 'text-ink-mute hover:bg-surface/60 hover:text-ink',
      )}
    >
      <item.Icon className={cn('h-3.5 w-3.5', active ? 'text-sky-400' : 'text-ink-faint')} />
      {item.label}
    </Link>
  )
}

export default function App() {
  const active = useActiveItem()

  return (
    <div className="min-h-full lg:grid lg:grid-cols-[16rem_minmax(0,1fr)]">
      <aside className="hidden border-r border-line lg:sticky lg:top-0 lg:flex lg:h-screen lg:flex-col">
        <div className="px-4 py-5">
          <Brand />
        </div>
        <nav className="flex-1 space-y-1 px-3">
          {NAV.map((item) => (
            <SidebarLink key={item.to} item={item} active={item.to === active.to} />
          ))}
        </nav>
        <div className="border-t border-line px-5 py-4 text-[11px] leading-relaxed text-ink-faint">
          Observer only — the harness never launches or schedules agents.
        </div>
      </aside>

      <div className="flex min-h-full min-w-0 flex-col">
        <header className="sticky top-0 z-20 border-b border-line bg-canvas/85 backdrop-blur">
          <div className="mx-auto w-full max-w-6xl px-4 md:px-8">
            <div className="py-3 lg:py-4">
              <Brand className="mb-3 lg:hidden" />
              <h1 className="truncate text-base font-semibold tracking-tight text-ink lg:text-lg">
                {active.title}
              </h1>
              <p className="mt-0.5 text-xs text-ink-mute">{active.description}</p>
            </div>
            <nav className="-mx-1 flex gap-1 overflow-x-auto px-1 pb-3 lg:hidden">
              {NAV.map((item) => (
                <MobileNavLink key={item.to} item={item} active={item.to === active.to} />
              ))}
            </nav>
          </div>
        </header>

        <main className="flex-1">
          <div className="mx-auto w-full max-w-6xl px-4 py-6 md:px-8 md:py-8">
            <Routes>
              <Route path="/" element={<Sessions />} />
              <Route path="/loops" element={<Loops />} />
              <Route path="/skills" element={<Skills />} />
              <Route path="/self" element={<Self />} />
              <Route path="/knowledge" element={<Knowledge />} />
            </Routes>
          </div>
        </main>
      </div>
    </div>
  )
}
