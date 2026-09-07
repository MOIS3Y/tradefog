# Interface Style Guide

## Purpose & Visual Direction

Tradefog uses a restrained, high-density interface built upon the Tabler UI
design system. The design emphasizes clarity, risk discipline, and rapid
data scanning over decorative elements.

A static reference implementation is available in `template/`.

## Layout & Shell

### Global Navigation Shell

- **Container**: `container-xl` fluid width across all screens.
- **Top Bar**: Brand logo, active context indicators, theme switcher
  (Dark / Light mode toggle with smooth animation), and user profile menu.
- **Main Navigation**: Dashboard/Home, Profiles, Trades, Analytics, Catalog,
  and Settings.
- **Footer**: Compact footer with documentation, changelog, and system status.

### Standard Page Structure

```text
┌─ Global Navigation ──────────────────────────────────────────────────┐
└──────────────────────────────────────────────────────────────────────┘
┌─ Page Header (container-xl) ─────────────────────────────────────────┐
│ PRETITLE / SECTION                                                   │
│ Page Title  [Help tooltip]                         [Primary Action]  │
└──────────────────────────────────────────────────────────────────────┘
┌─ Page Body (container-xl) ───────────────────────────────────────────┐
│ Page-specific content, filters, tables, and forms                    │
└──────────────────────────────────────────────────────────────────────┘
```

## UI Components & Patterns

### Collection Lists & Tables

- **Header Slot**: Result count (`23 items`), Filter toggle button, and
  Primary Action button (`+ Add item` with rotating plus animation).
- **Filter Panel**: Collapsible card above the table. Collapsed by default
  unless filters are actively applied. Contains reset and apply controls.
- **Data Table**: Wrapped in `card > table-responsive`, using
  `table table-vcenter card-table`.
- **Columns**: Most recognizable value first with secondary text in
  `text-secondary small`. Actions right-aligned in `btn-list flex-nowrap`.
- **Sorting**: Active sort column marked with `↑` or `↓`.
- **Pagination**: Dedicated footer with page indicator and navigation controls.

### Empty States

When a collection contains no items:
- Use `section.empty.empty-bordered`.
- Display a quiet icon, sentence-case title, explanatory subtitle, and an
  actionable primary button.
- Differentiate between a completely empty collection (calls to create first
  item) and an empty search/filter result (calls to reset filters).

### Forms & Modals

- **Simple Forms**: Centered column (`col-12 col-lg-8 col-xl-7`).
- **Form Controls**: Tabler form controls (`form-control`, `form-select`,
  `form-check-input`).
- **Field Hints**: Every field provides a concise contextual hint explaining
  domain impact.
- **Validation**: Inline error messages under invalid fields with clear error
  borders. Non-field errors displayed in an alert card.
- **Modals**: Used for quick atomic operations (deposits, withdrawals,
  catalog creation).

### Notifications & Feedback

- **Field Errors**: Rendered inline directly beneath the respective form field.
- **Toast Notifications**: Ephemeral status feedback (success / error alerts)
  rendered in a dedicated top-right toast container.

## Color System & Theming

- **Theme Support**: Seamless Dark and Light modes.
- **Palette Tokens**:
  - Primary: Brand accent for key actions and active navigation.
  - Success: Positive outcomes, winning trades (`result_r > 0`).
  - Danger: Stop loss levels, losing trades (`result_r < 0`), destructive
    actions.
  - Warning: Advisory alerts, break-even outcomes, approaching risk stops.
  - Secondary/Muted: Contextual hints, timestamps, secondary labels.

## Internationalization (i18n)

- All user-facing strings support English (default) and Russian.
- Translations managed client-side using standard i18n dictionaries.
- Numbers, currencies, and dates format according to the active locale.
