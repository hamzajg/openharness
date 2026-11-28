# ADR 0013 — Navigation surface as part of the experience contract

Status: accepted · 2026-11-27 · relates D019, ADR 0011, ADR 0012

## Context

ADR 0011 added `## Experience` to SPEC.md and ADR 0012 added a scan
pattern (`F-pattern | Z-pattern | single-column`). Together they say what
the journey is and how the page is scanned, but not **where the work
happens**. An agent can satisfy both and still implement the same edit as a
new route in one feature, a right-side pane in the next, and a centred
modal in a third, with no reviewable decision between them. Reviewers have
no shared vocabulary to challenge "open it in a drawer" or "make it a
popup", so the choice is made per wave and drifts.

The standards the project already cites (Material Design, Apple HIG,
Nielsen Norman Group, Shopify Polaris) differ visually but agree on the
task-fit question: a surface should preserve the user's context when the
task is subordinate to a list, become a destination when it is the work
itself, and interrupt only for short blocking decisions. That is enough to
make the choice explicit without adopting a design system.

## Decision

Add one required field to `## Experience`:

```
- Navigation/overlay: (full-page | side-pane | modal | inline; — rationale optional)
```

Vocabulary (one primary surface per journey):

- **`full-page`** — a routed destination that replaces the current view.
- **`side-pane`** — a right-side drawer/panel over the current page; the
  list or record behind it stays visible. `drawer` is accepted as an alias.
- **`modal`** — a centred, blocking dialog with the page inert.
- **`inline`** — editing in place, in the row, section or page body, with
  no separate surface.
- **`n/a — <reason>`** — only when no user-facing surface exists; a bare
  `n/a` is rejected, consistent with the rest of the section.

Depth scales with the `DOMAIN.md` tier:

| Tier | Required value |
|---|---|
| `simple` | the surface token |
| `standard` | `<surface> — <rationale>` |
| `domain-heavy` | `<surface> — <rationale citing a design standard>` |

The rationale explains why this surface was chosen over the alternatives
(e.g. "keeps the filtered list and scroll position visible while editing").
The citation list is the same one ADR 0012 uses (Material, Apple HIG, NN/g,
Polaris, Bootstrap, Fluent, Carbon, Ant Design, Tailwind). With no
`DOMAIN.md`/tier the depth check is skipped, so legacy specs stay valid.

`experience_status` enforces the vocabulary and tier depth; `ship_loop`
(G3 staleness and mark-time validation) and `review_delivery` share it, so
one validator covers both surfaces. The gate checks stay shallow. The spec
audit adds one advisory concern, `experience-surface-mismatch`, when the
primary journey uses explicit cues that contradict the declared surface
(a `modal` with browsing/edit cues, `inline` with a drawer or new page,
`full-page` with "without leaving"/"stays visible", `side-pane` with
"navigates to"/deep link). The finding names the matched cues; a reviewer
decides whether the conflict is real.

The decision rules — when a side pane beats a page, when a popup is
legitimate, and the behaviour a surface must implement — live in
`docs/frontend-page-guide.md`, which is normative for reviewers.

## Alternatives considered

- **A separate `DESIGN.md` artifact.** Rejected for now: the surface is one
  decision inside the experience contract; a second file adds a gate
  without adding a distinct decision. Revisit if visual tokens, spacing or
  component rules need the same treatment.
- **Two fields (`navigation` and `overlay`).** Rejected: it invites two
  primary surfaces for one journey. Secondary confirmations are named in
  the rationale and governed by the guide.
- **Free-text layout notes.** Rejected: no fixed vocabulary means no gate
  can distinguish a decision from a paragraph, and reviewers cannot compare
  features.
- **Hard bans by tier (e.g. no modal above `simple`).** Rejected: a short
  destructive confirmation is correct at every tier. Tier controls how
  much justification is required, not which surface is legal.
- **Review-only, no field.** Rejected for consistency with D019/ADR 0012:
  the decision is cheap at spec time and expensive to retrofit mid-wave.

## Consequences

- `spec_scaffold` emits the field; G3 names it. Fixtures and the six
  LoomLine specs were backfilled (the five `done-legacy` specs keep their
  gates and status; their record is now complete).
- `standard` and `domain-heavy` specs must write one clause of
  justification; the guide supplies the decision rules to cite.
- The guide and the validator must stay aligned: adding a surface means
  changing the regex, the scaffold, this ADR and the guide together.
- The audit's surface check is cue-based and advisory: it flags plain
  contradictions without trying to grade the fit, so a false positive is a
  prompt to sharpen the journey or the rationale, not a blocked wave.
- No new runtime module; `ship_loop` remains the only writer of loop state.
