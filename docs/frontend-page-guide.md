# Frontend page-building guide

How to choose the surface a user journey runs on, and what that surface must
do. This guide is the narrative behind the `Navigation/overlay` field in
SPEC.md's `## Experience` (ADR 0013). It is intentionally about structure, not
visual language: no tokens, palettes or component libraries.

**Rule of thumb:** use the lightest surface that preserves the user's context
and finishes the task. A surface is a decision, not a default.

## The four surfaces

| Token | What it is | Typical use |
|---|---|---|
| `full-page` | A routed destination that replaces the current view | Order detail, settings, a long create form, a report |
| `side-pane` | A right-side drawer/panel over the current page; content behind stays visible | Create/edit one record from a list, quick inspection, contextual editing |
| `modal` | A centred, blocking dialog; the page behind is inert | Short confirmation, destructive action, a 1–3 field decision |
| `inline` | Editing in place in the row, section or page body | Rename, quantity, status, a single setting |

`drawer` is an accepted alias for `side-pane`; prefer `side-pane` in specs so
reviewers can compare features. `n/a — <reason>` is only for a journey with no
user-facing surface.

## Decision order

Walk these in order and stop at the first that fits:

1. **No new surface?** If the change is one value in a row or section, use
   `inline`.
2. **Short, blocking decision?** If it must interrupt and is small (≤3 fields
   or yes/no), use `modal`.
3. **Destination?** If the view should be linkable, refreshable, shareable or
   is the main work for a while, use `full-page`.
4. **Subordinate task on existing context?** If the user starts from a list or
   record and returns to it, use `side-pane`.
5. **Still unclear?** Prefer `full-page` for anything long or multi-step and
   `side-pane` for anything short and contextual. Do not reach for `modal` to
   avoid designing a surface.

## Side pane vs. a new page

Choose a **side pane** when most of these are true:

- the task starts from a list, table, board or detail the user must keep
  seeing (compare, copy, check a sibling row);
- the form is moderate — roughly 3 to 12 fields, one record, one step;
- returning to the same filter, scroll position and selection matters;
- the task is occasional and subordinate to browsing, not a destination in
  the navigation;
- the user will open and close several records in a row;
- desktop or tablet width is available.

Choose a **full page** when any of these dominate:

- it is a destination users navigate to, not an action on a list;
- deep-linking, refresh, back/forward or sharing the state matters;
- the form is long, multi-section or multi-step, or needs its own tabs and
  related tables;
- the work is the main task for a sustained period (an order detail, a
  routing sheet, a reconciliation report);
- it is the primary flow on mobile;
- multiple records are edited at once, or the view is data-heavy.

In short: **the pane wins when context preservation beats addressability; the
page wins when addressability, depth or duration beats context.**

A side pane is not a page squeezed into a column. If the content needs its own
sub-navigation, breadcrumbs or more than one scroll region, make it a page.

## Side pane vs. popup/modal

Choose a **side pane** over a popup when:

- the user needs the underlying list or record visible while acting;
- the task is a real form rather than a decision — more than about three
  fields, validation summaries, or a save/cancel cycle;
- the work is not urgent enough to justify making the page inert;
- the user may want to check or copy from the page mid-task.

Choose a **modal** over a side pane only when:

- the decision is short and blocking — a confirmation, a destructive action,
  an acknowledgement;
- proceeding while the dialog is unresolved would be unsafe or incoherent;
- the user does not need to read the page behind it to answer.

A popup is the wrong tool for creating or editing a domain record. It is the
right tool for "delete this order?", "discard unsaved changes?", "publish
these 12 items?". If a popup grows a form, promote it to a side pane or a
page.

## Confirmations and destructive actions

- Use a small modal, name the object and the consequence, and label the action
  with the verb ("Delete order", not "OK").
- Put initial focus on the safe choice (Cancel) for destructive dialogs.
- Do not close a destructive dialog on outside click or Escape without an
  explicit cancel.
- Confirmations of success are not modals: use a toast, inline status or the
  updated row.
- If a side pane needs a destructive confirmation, use an inline confirmation
  band inside the pane rather than stacking a dialog over it.

## One surface per journey

Record **one** primary surface. Name secondary surfaces — a confirmation, a
picker, a preview — in the rationale and govern them with this guide. Do not
give one journey both a drawer and a page "depending on entry point"; pick the
primary one and make the other a link into it.

Never stack overlays: no modal over a side pane, no second drawer on top of
the first, no popup over a popup. If two overlays seem necessary, the first
one is hiding a missing page.

## Behaviour contract

Whatever the surface, implement these before calling it done:

**URL and history**
- `full-page`: a real route; refresh, deep link and back/forward work.
- `side-pane`: the surrounding page keeps its route; if the pane is
  addressable, encode the record in a query parameter (e.g. `?edit=42`) so
  refresh restores it and Back closes the pane before leaving the page.
- `modal`: no history entry unless the flow is itself deep-linkable; closing
  returns the user to the same scroll position.
- `inline`: no navigation; the edited row stays in place.

**Focus and dismissal**
- On open, move focus to the surface heading or first field; on close, return
  it to the control that opened it.
- `modal`: trap focus, set `role="dialog"` and `aria-modal="true"`, label it
  with its heading, and make the page inert.
- `side-pane`: do not trap focus unless it is a blocking modal drawer; keep it
  reachable by keyboard, close on Escape, and keep the background usable when
  the task allows it.
- Close on outside click only for non-modal surfaces with no unsaved changes.

**Unsaved work and errors**
- Guard closing when the form is dirty; confirm discard rather than losing
  input.
- A failed save keeps every entered value and shows field-level errors; never
  close the surface on failure.
- Disable the submit control while saving and make repeated clicks safe.

**Layout and motion**
- Side pane: clamp the width (roughly 360–560 px), never exceed the viewport,
  keep the header and actions visible while the body scrolls.
- Modal: roughly 480–640 px wide; short body; do not hide a required action
  below the fold.
- Full page: cap form width for readability; do not stretch inputs edge to
  edge on wide screens.
- Respect `prefers-reduced-motion`; animate entrance/exit, not content.

## Responsive

- Below the tablet breakpoint, a `side-pane` becomes a `full-page` (or a
  full-height sheet), not a modal floating over a list. Preserve the return
  path to the list's filter and scroll.
- A `modal` stays a dialog but may go near-fullscreen for short forms; keep
  the safe cancel and the labelled action visible.
- `inline` editing must not require horizontal scrolling; switch the row to a
  stacked layout when the table no longer fits.
- Decide the mobile behaviour in the spec's edge states, not during
  implementation.

## Accessibility checklist

- The surface has a programmatic name (heading + `aria-labelledby`).
- Focus moves in on open and returns to the trigger on close.
- Escape closes dismissible surfaces; nothing traps keyboard focus
  accidentally.
- Background content is inert only when the surface is genuinely modal.
- Every field has a visible label; errors are tied to fields and announced.
- Status is text, not colour alone; contrast and target sizes meet WCAG 2.1 AA.
- Body scroll is locked only when the background must not move, and the lock
  is released on close.
- Content remains usable at 200% zoom and with a keyboard only.

## Anti-patterns

- A drawer holding a 30-field entity — use a page.
- A modal for creating or editing a domain record — use a pane or page.
- A full page for renaming one field — use inline.
- A pane that loses the list's filter and scroll position on close.
- A drawer with no URL and no dirty-state guard.
- A modal that closes on outside click after edits or for a destructive action.
- A success modal, or a modal to show validation errors.
- Stacked overlays, or a drawer that opens another drawer.
- Recording two primary surfaces for one journey to avoid choosing.

## Recording the decision in SPEC.md

One line, under `## Experience`:

```
- Navigation/overlay: side-pane — keeps the filtered list, scroll position and
  sibling rows visible while editing one record; deleting an in-use row uses a
  small confirmation modal.
```

More examples:

| Journey | Value |
|---|---|
| Order list → create order | `full-page — the single-column create form is a routed page; the list keeps its own route and filters.` |
| Order detail → edit routing | `inline — the routing sheet is edited in place on the order detail; no separate route or drawer.` |
| Rename a saved view | `inline — one value saved in the row, with undo.` |
| Sign-in | `full-page — unauthenticated destination with a preserved return path.` |
| Delete an order | `modal — short, irreversible decision that must block until answered.` |

Tier depth: `simple` may give the token alone; `standard` must add the
rationale; `domain-heavy` must also cite the design standard the choice
follows. The validator checks only that the clause is present — reviewers
judge whether it is true.

## What the audit checks

`review_delivery` reads the two fields and raises an advisory
`experience-surface-mismatch` concern when the journey plainly contradicts
the surface: a `modal` journey that browses or edits a list or form, an
`inline` journey that opens a drawer or a new page, a `full-page` journey
that promises to keep the list visible, or a `side-pane` journey that
navigates to a separate route. The finding lists the cues it matched.

It is deliberately narrow and never blocks: a false positive is a prompt to
sharpen the journey wording or the rationale, not a verdict. Whether the
chosen surface is genuinely the right one remains the reviewer's call.

## Review checklist

1. Does the chosen surface match the decision order, is the rationale about
   context, depth or duration rather than taste, and is any
   surface-mismatch concern resolved?
2. Is there exactly one primary surface, with secondary dialogs named?
3. Are URL, Back, refresh and focus-return defined?
4. Is unsaved work protected, and does a failed save preserve input?
5. Is mobile behaviour specified as an edge state?
6. Are accessibility and dismissal rules satisfied?
