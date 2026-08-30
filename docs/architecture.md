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
├── journal/        # assets, profiles, pairs, trades, and calculations
├── config/         # typed application configuration and Django settings
├── templates/
└── static/
```

`journal` is the primary domain application. Analytics remains part of it
until analytics develops an independently complex responsibility.

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
```

HTMX responses are translated HTML fragments. Independently updated regions
use partial templates. Out-of-band swaps are suitable when one domain action
changes several independent fragments, such as plan, profile status, and
remaining risk.

The server remains the source of truth for persisted state. JavaScript is
limited to browser interactions that are awkward in server-rendered HTML.

## Frontend

Tabler UI is the component and layout system. Its standard palette,
documented components, Bootstrap utilities, validation states, and responsive
patterns define the established visual language. Tabler, HTMX, and selected
plugins are served locally; production pages do not depend on a CDN.

Templates use semantic HTML, accessible controls, and reusable partials where
they represent genuinely repeated interface structure. Custom styling and
JavaScript stay small and feature-driven.

List.js progressively enhances fully rendered journal tables with client-side
sorting. Sortable cells expose canonical values separately from localized
presentation, and HTMX replacements reinitialize the affected table. Lists
that later require server-side pagination also move their ordering to Django
query parameters instead of sorting only one rendered page.

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

## Logging

The standard Python `logging` API and Django `LOGGING` configuration own all
application logging. Uvicorn runs with `log_config=None` so it participates in
the same configuration.

Operational output goes to the console. Container or service runtimes are
responsible for retention. Django `DEBUG` and log level are independent.
Meaningful domain transitions, recoverable failures, and external integration
boundaries are logged without secrets or complete configuration objects.

## Exchange and market-data boundaries

The journal, lifecycle services, models, analytics, and primary interface are
shared by all execution providers. Manual and future Bybit profiles do not
fork the domain or page structure.

An exchange connection is distinct from a trading profile. One connection may
serve several virtual allocations. Exchange wallet balances are never the
source of truth for profile capital, although an adapter may check actual
balance before execution.

A future Bybit adapter extends the shared trade workspace with execution
controls and calls the same lifecycle operations as manual views. It may
place entry, stop, and take-profit orders, associate external identifiers,
synchronize state, and record final P&L. Journal review and attachments remain
common application behavior.

Provider credentials, execution modes, and external order identifiers enter
the schema only with the first working adapter. Exchange-specific code stays
behind a small service boundary and does not spread through templates,
analytics, or core models.

Market-data retrieval has a separate focused boundary. It can use public
provider data without requiring the execution adapter or account credentials.
On-demand requests use timeouts and cached fallback data.

## Persistence

SQLite is the initial database. ORM code remains portable enough for a later
PostgreSQL migration, without depending on PostgreSQL-specific behavior.

Calculated statistics are derived from stored trade facts until measurement
shows a need for denormalization. Persisted calculated values exist only when
they preserve decision context or historical reproducibility, such as risk
snapshots on submitted trades.

Multi-model domain transitions use database transactions when atomicity is
required. Ownership is enforced at query boundaries, and database constraints
back important invariants where practical.

## Security

The application uses Django authentication, CSRF protection, and standard
security mechanisms. Exchange keys, API secrets, session secrets, and
production environment files are never repository content or log data.

Future exchange credentials request only the permissions needed for supported
execution. Withdrawal permission is not part of journal automation.

Attachments are private by default. External failures cannot corrupt journal
state, and the manual journal remains usable when an exchange or market-data
provider is unavailable.

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
