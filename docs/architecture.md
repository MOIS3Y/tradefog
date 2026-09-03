# Tradefog architecture

## System shape

Tradefog is a Django application with server-rendered HTML and focused HTMX
updates. The initial deployment is a single process and a single database.
The architecture favors explicit Django conventions and small domain services
over generic infrastructure.

The initial stack is:

- Python and Django;
- Django templates and HTMX;
- Tabler UI, vendored locally;
- SQLite;
- Uvicorn for the standalone ASGI server;
- `uv` for Python dependencies;
- Nix flakes and `uv2nix` for development and packaging.

There is no frontend framework, REST framework, task queue, message broker, or
distributed service in the initial system.

## Application layout

The codebase uses a small number of cohesive Django applications:

```text
tradefog/
├── accounts/       # custom user model and authentication
├── journal/        # profiles, strategies, instruments, trades, calculations
├── config/         # typed application configuration and Django settings
├── templates/
└── static/
```

`journal` is the primary domain application. Analytics remains part of it
until analytics develops an independently complex responsibility. Its modules
may be reorganized into cohesive subpackages for wallet, profiles, markets,
trades, analytics, and review rather than growing as flat files.

The intended dependency direction is:

```text
HTTP view
    |
    v
application/domain service
    |
    v
models and pure domain calculations
```

Templates render state but do not calculate trading rules. Views validate
transport input, call application or domain operations, and render full pages
or fragments. Pure formulas remain independently testable.

## Django and HTMX

HTMX supplies reactive server-driven behavior such as:

- recalculating a position plan;
- updating checklist progress and assessment;
- refreshing ATR context;
- changing lifecycle state;
- closing a trade;
- refreshing statistics and filtered lists.

Distinct actions use focused endpoints rather than a single view containing a
large conditional state machine. Typical routes include:

```text
/trades/
/trades/new/
/trades/<id>/
/trades/<id>/checklist/
/trades/<id>/plan/
/trades/<id>/submit/
/trades/<id>/open/
/trades/<id>/cancel/
/trades/<id>/close/
/analytics/
/profiles/<id>/instruments/
```

HTMX responses are translated HTML fragments. Independently updated regions
use partial templates. Out-of-band swaps are suitable when one domain action
changes several independent fragments, such as plan, strategy status, and
remaining risk.

The server remains the source of truth for persisted state. JavaScript is
limited to browser interactions that are awkward in server-rendered HTML.

## Frontend

Tabler UI is the component and layout system. Its vertical fluid layout and
standard palette,
documented components, Bootstrap utilities, validation states, and responsive
patterns define the established visual language. Tabler, HTMX, and selected
plugins are served locally; production pages do not depend on a CDN.

Detailed page composition and presentation rules live in
[`style-guide.md`](style-guide.md). This section records architectural
boundaries; the style guide is authoritative for shared interface patterns.

Templates use semantic HTML, accessible controls, and reusable partials where
they represent genuinely repeated interface structure. Custom styling and
JavaScript stay small and feature-driven.

Every visible form control has a concise contextual hint that explains its
domain meaning, effect, or expected format. Hints are linked to their controls
with `aria-describedby`; they do not merely repeat field labels.

Top-level journal sections use one shared page-heading partial: a direction,
title, and keyboard-accessible help-circle tooltip that explains the section's
purpose. Contextual forms and object-detail screens retain task-specific
headers.

The authenticated shell uses Tabler's sticky horizontal navigation in a shared
`container-xl` layout. Its upper bar contains the Tradefog brand, theme
control, and user menu with a placeholder avatar. Its Settings item is a
disabled placeholder until account settings are designed. The second bar
contains Home, Profiles, Trades, Analytics, and Settings. Profile detail
navigation contains Overview, Instruments, Wallet, Strategies, Trades, and
Settings. The trade workspace has a persistent context line for profile,
strategy, pair, fixed monetary `1R`, and available wallet funds. A compact
footer links to documentation, changelog, source, and sponsorship.

Operational journal lists use Django query parameters for sorting,
filtering, and pagination. Non-analytics list filters use one shared,
collapsed-by-default two-column panel; active values and validation errors
keep it open. HTMX replaces only the affected result region,
while the same URL remains directly navigable and refreshable. Tables sharing
a profile page use independent parameter names so instruments and wallet
activity do not reset one another. List.js remains limited
to the current analytics table until that interface is revisited with its
full filtering context.

The wallet belongs to one trading profile. Deposit and withdrawal controls
live on the relevant asset card and load a server-rendered form into a small
HTMX-powered Tabler modal. Its immutable activity table uses server-side
asset, operation, and date filters, sorting, and pagination through the same
URL.

Material interface work follows the project's restrained, risk-discipline
visual direction. New decoration is tied to useful information rather than a
generic dashboard aesthetic.

## Localization

English is the source and fallback language. Russian is the second supported
language. This language set and English default are fixed application
behavior rather than deployment configuration.

Every user-facing route has a language prefix, including English. Django
`i18n_patterns()` provides routes such as `/en/trades/` and `/ru/trades/`.
Route segments remain stable English identifiers.

The URL prefix is the source of truth for request language. The language
switcher navigates to the same named route under the selected prefix and
refreshes the full page. Links, form actions, and HTMX URLs use Django URL
reversing rather than string concatenation.

Server-rendered text and HTML attributes use gettext. Small translated values
needed by JavaScript are carried through escaped `data-*` attributes or
`json_script`. A language-prefixed `djangojs` catalog is available when
substantial client-side translation becomes necessary.

Tracked `.po` files are translation source. Compiled `.mo` files are build
artifacts produced during wheel and Nix builds, not by runtime setup or
`collectstatic`.

## Configuration and runtime data

Typed configuration models form the source of truth consumed by Django
settings. User configuration can be read from `settings.toml` in the XDG
configuration location or an explicit environment-selected path. Environment
values override file values and built-in fallbacks.

Runtime configuration, data, cache, state, static, and media paths follow XDG
locations. The development shell points at the repository-local runtime tree
and example configuration so local state stays isolated from the repository
layout.

Static resources and private media are separate. Collected static files may
be served by the standalone application. Uploaded screenshots live under the
configured media location but are not mounted publicly; authenticated Django
views enforce trade ownership before serving them.

Trade descriptions persist Markdown as their source representation. A
locally vendored EasyMDE editor enhances the ordinary Django textarea in
place and follows the active Tabler light or dark theme. DOMPurify sanitizes
the optional client-side preview; persisted Markdown is rendered on the
server without raw HTML or embedded images. Attachment uploads use purposeful
JavaScript for per-file progress and replace local previews with
server-rendered fragments. Description saves replace the editor with the same
safe server-rendered Markdown without reloading the trade; ordinary form POST
remains the no-JavaScript fallback.

The media configuration includes a default per-attachment size limit in MiB.
Zero disables this application-level limit for deployments that choose to
rely on their reverse proxy or storage constraints.

## Logging

The standard Python `logging` API and Django `LOGGING` configuration own all
application logging. Uvicorn runs with `log_config=None` so it participates in
the same configuration.

Operational output goes to the console. Container or service runtimes are
responsible for retention. Django `DEBUG` and log level are independent.
Meaningful domain transitions, recoverable failures, and external integration
boundaries are logged without secrets or complete configuration objects.

## Integration boundaries

Manual journal execution is the only current execution workflow. Tradefog does
not yet hold venue credentials, submit orders, or synchronize positions. The
shared reference catalog is staff-managed and deliberately curated rather than
bulk-synchronized. Regular users read and reuse catalog facts but do not
create or edit them. The profile-scoped virtual wallet remains authoritative
for journal availability and reservations.

Market data is an on-demand read-only boundary. It does not persist candles or
feeds in the database. In the trade workspace the user selects a provider and
the journal fetches the last closed daily candles on demand, computes
`ATR(14)`, and stores only an ATR decision snapshot (`AUTO` or `MANUAL`
source) on a submitted trade. Providers are `BYBIT` and `TWELVE_DATA`; an
instrument without a source may use a manually entered `MANUAL` ATR value, and
an instrument with no source and no value reports `N/A`. Provider failure
cannot block manual journaling and never corrupts catalog or journal state.

There are two independent provider responsibilities:

- an on-demand market-data provider fetches daily candles for ATR context in
  the trade workspace;
- a future execution adapter submits and synchronizes orders through a
  configured profile connection.

A market-data provider's external symbol or quote currency cannot redefine the
shared venue instrument or its settlement asset. The on-demand HTTPX clients
use explicit timeouts; provider selection and refresh authorization remain in
the market-data service, while True Range and ATR remain pure calculations.

Future order submission is a focused execution boundary. A user owns a list
of named API keys rather than a key bound to a venue; a trading profile
selects the key it uses. Manual actions remain available when no key or
adapter exists. Before any manual or automatic transition to pending or open,
the shared domain service verifies that the trade's venue instrument settlement
asset exactly equals the strategy settlement wallet asset. Adapter failure
leaves the journal decision unchanged and cannot make manual journaling
unavailable.

## Future automation

Automated order placement is a deferred, additive extension, not part of the
initial journal. It is not modeled in the current database; it is documented
here so the schema stays forward-compatible without speculative fields.

When it ships, order placement is limited to selected venues (initially Bybit)
and is a one-shot convenience action, not a tracking system:

- the user owns a list of named API keys, each a user-scoped credential that
  a profile selects; keys are encrypted at rest, never logged or returned, and
  grant trading permissions only — withdrawal is never requested;
- placing an order calls the venue once, records the venue order reference on
  the trade, and leaves execution outcome to the manual journal;
- there is no background execution tracking: no order, position, or fill
  tables, no polling, no webhooks, and no execution synchronization. The
  journal remains the source of truth;
- the extension is additive: adapters never alter past trades, and an API
  failure leaves the draft unchanged so manual journaling is never blocked.

TradingView, if ever added, is an opt-in external visual embed with visible
attribution. It is not an ATR source and must not become a required runtime
dependency for the journal.

## Persistence

SQLite is the initial database. ORM code remains portable enough for a later
PostgreSQL migration, without depending on PostgreSQL-specific behavior.

Calculated wallet balances, strategy equity, reservations, and statistics are
derived from stored facts until measurement shows a need for denormalization.
Persisted calculated values exist only when they preserve decision context or
historical reproducibility, such as risk and ATR snapshots on submitted
trades.

Market data is not persisted. Candles are fetched on demand in the trade
workspace, so there is no candle table to clean up and no stale cache.

Multi-model domain transitions use database transactions when atomicity is
required. Owner scoping is enforced at journal query boundaries, and database
constraints back important invariants where practical. Shared catalog records
referenced by journal data are retained for history; delisting and staff
removal change availability rather than destroying identities.

## Security

The application uses Django authentication, CSRF protection, and standard
security mechanisms. Exchange keys, API secrets, session secrets, and
production environment files are never repository content or log data.

Attachments are private by default. External failures cannot corrupt journal
state, and the manual journal remains usable when a market-data provider is
unavailable.

## Development and packaging

`pyproject.toml` and `uv.lock` are the source of truth for Python dependencies.
The development workflow uses `uv` directly.

`flake.nix` provides the reproducible shell, package, application, and
container outputs. Its Python environment is built with `pyproject-nix` and
`uv2nix`, so application package versions come from the Python project rather
than Python packages in nixpkgs. System-level development and build tools,
including GNU gettext and Dart Sass, come from Nix.

The flake inputs currently include:

- `nixpkgs`;
- `flake-utils`;
- `pyproject-nix`;
- `uv2nix`;
- `pyproject-build-systems`.

Application assets are built without a Node.js toolchain. Tabler and HTMX are
vendored, SCSS is compiled by Dart Sass, and the selected SVG icon sprite is
generated as a package build step.

The container runs as an unprivileged user and uses `/app` for mounted runtime
state. Migrations and static collection are explicit setup actions rather than
implicit server startup behavior.

## Dependency strategy

The dependency set remains intentionally small. New libraries are justified
by a current requirement and by meaningful complexity they remove.

The following remain deferred until a concrete consumer or operational need
exists:

- Django REST Framework;
- Celery, Redis, and Channels;
- CCXT;
- frontend frameworks;
- PostgreSQL-specific libraries;
- additional Nix abstraction frameworks.

Simple chart JSON or HTMX endpoints do not require Django REST Framework. A
real mobile, desktop, CLI, third-party, or service API consumer would justify
reconsidering it.

## Architectural constraints

The system intentionally avoids speculative repositories over the Django ORM,
single-implementation abstract base classes, event or command buses, CQRS,
microservices, plugin systems, generic rule engines, dependency-injection
frameworks, and distributed task infrastructure.

Abstractions enter the codebase in response to concrete variation. The first
working implementation remains explicit and easy to change.
