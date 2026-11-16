import type { ReactNode } from 'react'

export interface IconProps {
  className?: string
}

/** One stroke style for every icon: 16px box, currentColor, 1.5px stroke. */
function Svg({ className, children }: IconProps & { children: ReactNode }) {
  return (
    <svg
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.5}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden="true"
    >
      {children}
    </svg>
  )
}

export const IconSessions = (p: IconProps) => (
  <Svg {...p}>
    <rect x="1.75" y="2.75" width="12.5" height="10.5" rx="1.75" />
    <path d="M4.5 6.5l2 1.75-2 1.75" />
    <path d="M8.25 10h3.25" />
  </Svg>
)

export const IconLoops = (p: IconProps) => (
  <Svg {...p}>
    <path d="M1.5 8h2.5l2-4 2.5 8 2-4h4" />
  </Svg>
)

export const IconSkills = (p: IconProps) => (
  <Svg {...p}>
    <path d="M8.75 1.5L3.5 9h3.25l-.5 5.5L11.5 7H8.25z" />
  </Svg>
)

export const IconSelf = (p: IconProps) => (
  <Svg {...p}>
    <path d="M8 1.75l5.25 2v4.5c0 3-2.25 5-5.25 6-3-1-5.25-3-5.25-6v-4.5z" />
    <path d="M6 8l1.5 1.5L10.5 6.5" />
  </Svg>
)

export const IconKnowledge = (p: IconProps) => (
  <Svg {...p}>
    <circle cx="7.25" cy="7.25" r="4.5" />
    <path d="M10.5 10.5L14 14" />
  </Svg>
)

export const IconClose = (p: IconProps) => (
  <Svg {...p}>
    <path d="M4 4l8 8M12 4l-8 8" />
  </Svg>
)

export const IconChevronRight = (p: IconProps) => (
  <Svg {...p}>
    <path d="M6 3.5L10.5 8 6 12.5" />
  </Svg>
)

export const IconPlay = (p: IconProps) => (
  <Svg {...p}>
    <path d="M5.5 3.5l7 4.5-7 4.5z" />
  </Svg>
)

export const IconRefresh = (p: IconProps) => (
  <Svg {...p}>
    <path d="M13.5 8a5.5 5.5 0 1 1-1.6-3.9" />
    <path d="M13.5 2.5V5H11" />
  </Svg>
)

export const IconAlert = (p: IconProps) => (
  <Svg {...p}>
    <path d="M8 2.25L14.25 13H1.75z" />
    <path d="M8 6.5v3" />
    <path d="M8 11.25h.01" />
  </Svg>
)

export const IconCheck = (p: IconProps) => (
  <Svg {...p}>
    <path d="M3 8.5l3 3 7-7.5" />
  </Svg>
)
