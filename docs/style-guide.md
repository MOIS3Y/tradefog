# Interface Style Guide

Tradefog uses a single dark interface built for focused trading-journal work.
The visual language is quiet and dense enough for data, with restrained green
accents reserved for active state, selection, and primary actions.

## Foundations

- IBM Plex Sans is the interface face; IBM Plex Mono is limited to symbols,
  prices, ratios, compact labels, and other market data.
- Semantic `--tf-*` tokens define color, radii, elevation, and typography.
- Surfaces use soft borders, rounded corners, subtle gradients, and limited
  glow. Red communicates destructive or failed actions.
- Lucide icons support meaning and never replace a necessary text label.

## Interaction Patterns

- Primary actions sit in section headers; row actions use compact icon buttons
  with accessible labels.
- Native selects are avoided. Fixed options use `AppSelect`; growing entity
  catalogs use `SearchableSelect`.
- Table sorting lives in column headers and exposes `aria-sort`. Search,
  visibility, and type filters remain client-side until server pagination.
- Create and edit forms open in a right-side canvas. Destructive actions use a
  confirmation dialog; reversible archive actions remain visually quieter.
- Permanent deletion is offered only for archived records. The API remains the
  authority on whether journal references make deletion unsafe.
- Wallet operations are presented as ledger facts. Their financial fields have
  no edit affordance; note correction opens a note-only form.
- Success and failure use stacked, dismissible toasts in the lower-right corner.

## Content and States

- Headings may have one short explanatory sentence when the domain term is not
  self-evident. Avoid stage labels, decorative numbering, and setup copy that
  becomes noise during routine use.
- Empty states name what is absent and offer the next valid action. Dependency
  gaps link to the catalog section that resolves them.
- Staff controls are hidden from regular users; catalog data remains readable.
- Archived records remain discoverable through a status filter and use muted
  badges rather than destructive styling.
- Exact decimal strings are displayed without insignificant trailing zeroes and
  are never converted through JavaScript floating-point numbers.

## Responsive Behavior

- Desktop tables become labeled record cards below 620 px.
- Split workspaces stack on small screens, with horizontal entity selectors
  where preserving context is useful.
- Keyboard focus is always visible and reduced-motion preferences are honored.
