# Interface Style Guide

Tradefog uses a single dark interface built for focused trading-journal work.
The visual language is quiet and dense enough for data, with restrained green
accents reserved for active state, selection, and primary actions.

## Foundations

- IBM Plex Sans is the interface face; IBM Plex Mono is limited to symbols,
  prices, ratios, compact labels, and other market data.
- Each authenticated page has one 20–24 px heading inside a bordered panel,
  with a green semantic icon, muted description and actions. Avoid a second
  title above the panel; retain an accessible h1 and trade back navigation.
- Authenticated workspaces fill the available width beside the navigation;
  outer horizontal padding is 24 px, or 14 px at mobile widths up to 620 px.
  Reading text, authentication forms and dialogs retain their own width limits.
- Semantic `--tf-*` tokens define color, radii, elevation, and typography.
- Surfaces use soft borders, rounded corners, subtle gradients, and limited
  glow. Red communicates destructive or failed actions.
- Lucide icons support meaning and never replace a necessary text label.

## Interaction Patterns

- Primary actions sit in section headers; row actions use compact icon buttons
  with accessible labels.
- Native selects are avoided. Fixed options use `AppSelect`; growing entity
  catalogs use `SearchableSelect`.
- Table sorting lives in column headers and exposes `aria-sort`. Catalog and
  trade search, filtering and sorting run on the server before pagination.
  Tables offer 25, 50 or 100 rows per page and show the filtered total.
- Pagination uses accessible chevron buttons and a compact page-size selector.
  Profile directories keep pagination at the panel bottom on
  desktop and below the horizontally scrolling cards on mobile. All lists
  hide pagination when the filtered total is at most 25, page is 1 and page
  size is 25. Larger sizes and stale higher pages keep navigation available.
- Additional trade filters collapse behind “More filters”, with an active
  count. Reset remains visible; collapsing the panel preserves its filters.
- Large catalog selectors search remotely and load additional pages on demand;
  the selected identity resolves independently of the current options page.
- Create and edit forms open in a right-side canvas. Destructive actions use a
  confirmation dialog; reversible archive actions remain visually quieter.
- Permanent deletion is offered only for archived records. The API remains the
  authority on whether journal references make deletion unsafe.
- Wallet operations are presented as ledger facts. Their financial fields have
  no edit affordance; note correction opens a note-only form.
- Success and failure use stacked, dismissible toasts in the lower-right corner.
- The trade list provides cross-profile navigation; each trade opens on its
  own page, grouping position, checklist, volatility, notes and images by task.
- Lifecycle actions follow draft, pending entry, open, closed or cancelled;
  immutable snapshot values receive no edit affordance after submission.
- ATR bars share a visible 75% marker. Exceeding it is advisory and changes the
  visual warning state without blocking a discretionary draft.
- Position inputs follow stop, entry, and derived target order. The target is
  read-only; the risk map keeps stop and target labels at opposite edges and
  places entry at the exact `1:R` boundary.
- Trade notes and screenshots share one journal module. Private image blobs
  open in a keyboard-accessible full-screen gallery and are revoked locally.
- Supported markets add chart, current order book, and position parameters
  side by side on wide screens. Mobile stacks them in that order, with a
  collapsible book. Unsupported providers retain the full-width position form.
  Market errors never disable journal controls; drawings are browser-local.
  The same position component fills the available width for manual markets.
  Spot/cash sale-and-buyback displays inventory and cash risk reserves separately.
  Book side switches only change presentation, never request frequency.

## Content and States

- Headings may have one short explanatory sentence when the domain term is not
  self-evident. Avoid stage labels, decorative numbering, and setup copy that
  becomes noise during routine use.
- Empty states name what is absent and offer the next valid action. Dependency
  gaps point to the profile section that resolves them.
- Empty profiles and trades distinguish first use, archived-only profiles and
  filtered results. First use offers setup; filtered results offer reset.
  Sorting, pagination and expanded filter panels are not filtering conditions.
  Resolve profile presence before showing setup guidance; loading, API errors
  and invalid date intervals must never masquerade as empty collections.
- Market setup is owner-scoped inside a profile. Bybit imports specs; manual
  profiles create instruments from separate asset symbols. No staff catalog is required.
- Archived records remain discoverable through a status filter and use muted
  badges rather than destructive styling.
- Exact decimal strings are displayed without insignificant trailing zeroes and
  are never converted through JavaScript floating-point numbers.
- Trade detail shows recorded lifecycle timestamps separately from the
  analytical trade date. UTC timestamps render in local time with seconds,
  localized dates and a 24-hour clock; absent events are omitted.
- Analytics labels offer a quiet help icon. Click or keyboard activation opens
  a dismissible explanation with a concrete example; help stays hidden during
  routine use.

## Responsive Behavior

- Desktop tables become labeled record cards below 620 px.
- Split workspaces stack on small screens, with horizontal entity selectors
  where preserving context is useful.
- Keyboard focus is always visible and reduced-motion preferences are honored.

- Pair-first setup uses existing compact forms and searchable symbol fields with
  an explicit Create symbol option. Newly created symbols expose an asset type.
- Asset names and funding live in the wallet, not a second market catalog.
  A Hide empty balances switch is on by default and hides never-used assets,
  not historical denominations that reached zero. Cards form an adaptive grid
  of at most six columns, or a horizontally scrolling mobile row. Each card
  contains all balance metrics and sibling selection/action controls, without
  nested buttons or a duplicated summary. The ledger follows the selected
  asset, keeps kind/date filters and resets its page on selection changes.
  Asset type filters run on the server alongside search and empty-balance
  filtering, before pagination. Instrument rows display base/quote asset
  types from the linked assets, not duplicated instrument metadata. Use
  existing green/blue/amber type badges for crypto/fiat/equity. Wallet cards
  show “Name · Type”, or only the type when unnamed. Bybit type filters omit
  equity. Ledger type and signed amount use green for deposits and red for
  withdrawals; both date and operation type support server-side sorting.
  Search, type filtering and pagination select the first visible asset if necessary; explicit
  funding navigation can pin an off-page asset. Financial facts remain
  immutable, notes editable.
- Optional profile venue URLs open as separate browser links with noopener
  and noreferrer. Only credential-free HTTP(S) URLs are accepted; they never
  alter integration transports or chart instrument links.
- Composite selects and search fields draw focus on their outer shell only;
  inner inputs/triggers do not add another border, outline or glow. Plain
  fields and selects use the same thin green focus treatment. Wallet ledger
  filters are 40 px high, including the square reset action.
- Radio inputs and switches share explicit selection, disabled and keyboard
  focus states. Exact decimal presentation expands scientific notation.
