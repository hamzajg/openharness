# ADR 0014 — Design tokens and shared primitives for the observer UI

Status: accepted · 2026-11-28 · relates to ADR 0012, ADR 0013,
`docs/frontend-page-guide.md`

## Context

ADR 0012 and ADR 0013 make the *surface* and *scan pattern* reviewable, but
deliberately say nothing about visual language. In the observer UI
(`openharness/web`) that left three gaps:

- **Two competing theme sources.** Tailwind v4 is CSS-first (`@import
  "tailwindcss"` + `@theme`), yet a Tailwind v3 `tailwind.config.ts` sat
  beside it with `content`, an undefined `var(--radius)`, HSL variables that
  were never defined, and camel-cased duplicates of the CSS tokens. It was
  dead under v4 and misleading to anyone editing styles.
- **Raw palette classes.** Semantic tokens covered neutrals only; status
  colour was written as `sky-500`, `emerald-400`, `amber-500`, `red-300` …
  scattered across primitives and pages, so one meaning had several shades
  and a palette change meant a sweep.
- **The guide's behaviour contract was not met by the shared `Drawer`.**
  Every side pane rendered `role="dialog"` + `aria-modal="true"`, locked
  body scroll and could be dismissed by a full-screen backdrop click, while
  providing no focus return to the triggering row and no `aria-labelledby`.
  `Field` rendered a label but could not associate an error; `Button`
  defaulted to `type="submit"`.

The community standards the project already cites (Material, Apple HIG,
NN/g, Polaris) agree on the essentials: semantic tokens, one primary action
per surface, visible focus, labelled controls, errors tied to fields, and
AA contrast.

## Decision

1. **One theme source.** `src/index.css` `@theme` is the only theme
   definition. There is no `tailwind.config.ts`. It declares the neutral
   ink/line tokens, `--font-sans` / `--font-mono`, and semantic accents:
   `accent` / `accent-hover` (text, icons, links), `accent-strong` /
   `accent-strong-hover` (primary button fill), and `info` / `ok` / `warn` /
   `danger` / `alt` for status. Components use these names with Tailwind's
   opacity modifier (`bg-ok/10`, `ring-warn/30`); raw palette classes are
   not used in `src`.
2. **AA contrast is a token property.** `--color-ink-faint` is `#818181`
   (5.08:1 on canvas, 4.60:1 on surface) so hints and timestamps meet
   4.5:1; `#525252` (2.6:1) was removed. Every status token and ink token
   is AA on both backgrounds.
3. **Primitives carry the behaviour contract.** `Drawer` is a non-modal
   side pane by default: no `aria-modal`, no focus trap, no body-scroll
   lock, focus moves to the labelled pane on open and returns to the
   trigger on close, Escape and backdrop dismissal are configurable, and
   width is clamped to 440–560 px. `modal` opts into `aria-modal`, a focus
   trap and scroll lock. `Field` wires `id`, `aria-describedby`,
   `aria-invalid` and a `role="alert"` error to `Input`; `Button` defaults
   to `type="button"`; `SegmentedControl` is a labelled `role="group"`.
4. **Shell landmarks.** A skip link targets `<main id="main">`; both navs
   are labelled; decorative dots and progress bars are `aria-hidden` and
   colour-only status is paired with text.
5. **Motion is optional.** `prefers-reduced-motion: reduce` collapses
   animations and transitions, not just the drawer keyframes.

## Alternatives considered

- **Keep `tailwind.config.ts` and add `@config`.** Rejected: v4 CSS-first
  already works; keeping two sources preserves the drift the tokens were
  meant to end.
- **One token per raw shade (`sky-300`, `sky-400`, …).** Rejected: it
  renames the palette without making meaning semantic, and still lets two
  pages choose different shades for the same state.
- **Full design-system file (`DESIGN.md`).** Rejected for now: the tokens
  and primitives are the contract; a separate gate would not be enforced by
  anything and ADR 0012/0013 already own the surface vocabulary.
- **Keep `aria-modal` on every pane.** Rejected: it tells assistive tech
  the background is inert when it is not, contradicting the guide's
  side-pane rule.

## Consequences

- A palette change is one edit in `@theme`; a new status state adds one
  token and one `Tone`.
- Reviewers can check the guide's checklist against primitives instead of
  every page: focus return, labelled dialog, error association and
  dismissal rules live in `ui.tsx`.
- Deleting `tailwind.config.ts` is safe: it was untracked and unreferenced.
- These checks remain structural/advisory — whether a chosen colour or
  surface is *well designed* is still the reviewer's call. The web app has
  no test suite; `npm run build` (tsc + vite) is the mechanical gate.
