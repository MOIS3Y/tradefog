# Interface style guide

## Purpose

Tradefog uses a restrained Tabler interface. The journal should feel stable,
precise, and predictable: hierarchy comes from structure and spacing rather
than decoration. This guide is the source of truth for page composition and
repeated presentation patterns.

Use locally vendored Tabler components and Bootstrap utilities first. Add a
`tf-` class only when the application needs behavior or meaning that the
existing component system does not provide. All examples below are structural
schemes, not literal copy or fixed-width specifications.

## Shared page frame

Every authenticated page uses the shared shell from `tradefog/base.html` and a
`container-xl`. A page header belongs in the `page_header` template block,
before `main.page-body`. Page content, forms, filters, and HTMX result regions
belong in the `content` block.

This boundary keeps titles and page actions at the same vertical position on
list, form, and detail pages:

```text
┌─ application navigation ─────────────────────────────────────────────┐
└─────────────────────────────────────────────────────────────────────┘
┌─ page-header / container-xl ─────────────────────────────────────────┐
│ DIRECTION                                                            │
│ Page title  [purpose tooltip]                    [Page action]        │
└─────────────────────────────────────────────────────────────────────┘

┌─ page-body / container-xl ───────────────────────────────────────────┐
│ Page-specific content                                                │
└─────────────────────────────────────────────────────────────────────┘
```

Do not put a page title in a form card. Do not repeat the page title as a card
title unless the card describes a genuinely distinct subsection.

## Section headers

A top-level section header has three semantic parts:

1. a short direction in `page-pretitle`, such as `Journal`, `Quality`, or
   `Settings`;
2. one `page-title` that names the current section;
3. a concise explanation available from the title as a keyboard-accessible
   tooltip.

Render this combination through
`tradefog/components/page_heading.html`. The title uses `tf-page-heading`, is
focusable, and receives its explanation through the Tabler tooltip behavior.
The help text explains the section's purpose; it does not repeat the title.

Place the primary page action in `col-auto ms-auto` beside the heading column.
Use `row g-2 align-items-center` so the action wraps cleanly on narrow screens.
Creation actions use a primary button and the established rotating plus:

```html
<a class="btn btn-primary btn-animate-icon btn-animate-icon-rotate" ...>
  <!-- plus icon with class="icon-2" -->
  Add ...
</a>
```

Use one primary page action. Secondary navigation may use a neutral button,
but should not compete visually with the primary action. Actions that belong
to a table row remain in that row rather than in the page header.

Form and detail pages retain the same header position. Their direction names
the parent context, such as the profile name or `Configuration`, and their
title names the current task or object.

## Collection pages

Operational collections use server-side filtering, sorting, and pagination.
Their default composition is:

```text
DIRECTION
Collection title  [purpose tooltip]                         [+ Add item]

┌─ Filters ────────────────────────────────────────────────────────────┐
│ expanded only when requested, active, or invalid                     │
└─────────────────────────────────────────────────────────────────────┘

23 items
┌─ card ───────────────────────────────────────────────────────────────┐
│ Name ↑             Type               State               Actions    │
├─────────────────────────────────────────────────────────────────────┤
│ Primary value      Secondary data     Badge                 [⋯]      │
│ Supporting value                                                     │
├─────────────────────────────────────────────────────────────────────┤
│ Page 1 of 3                                      [Previous] [Next]  │
└─────────────────────────────────────────────────────────────────────┘
```

Show the result count immediately above the table. Wrap the table in
`card > table-responsive` and use `table table-vcenter card-table`. Prefer
short, stable columns. Put the most recognizable value first and render its
supporting value with `text-secondary small`. Keep row actions right-aligned
in `btn-list flex-nowrap`.

Icon-only actions require an accessible name. Mutating actions use a POST form
with CSRF protection. When an action is unavailable, use a genuinely disabled
control with `disabled` and `aria-disabled="true"`, and explain the prerequisite
in nearby help text or a tooltip.

## Filters

Use `tradefog/components/filter_panel.html` for non-analytics collection
filters. The panel is a GET form inside collapsed `details.card.card-sm`:

```text
┌─ Filters                                      [Active]          [›] ─┐
│                                                                  │
│ Label                          Label                              │
│ [control                   ]   [control                       ]   │
│ Contextual hint                Contextual hint                    │
│                                                                  │
│                                  [Reset filters] [Apply]          │
└──────────────────────────────────────────────────────────────────┘
```

The panel is closed by default and opens when a filter is active or validation
fails. Controls use one column on small screens and two columns from the
`md` breakpoint. Each field has a concise contextual hint and visible errors.

The form must work as a normal navigable GET request. HTMX progressively
enhances it with `hx-get`, `hx-target`, `hx-swap="outerHTML"`, and
`hx-push-url="true"`. Reset is a normal link to the collection URL. The server
validates parameters, applies owner scoping, and supplies the canonical filter
state.

## Sorting and pagination

Sortable headers are links, not client-side table controls. Use
`tf-sort-link`; add `active` to the selected column and `aria-sort` to its
`th`. Show `↑` or `↓` only for the active sort. A new sort preserves active
filters and resets pagination.

Pagination lives in the table card footer and uses the shared
`journal/partials/pagination.html` partial. Pagination links preserve filters
and sorting. Collections placed independently on the same page use distinct
query-parameter names so one collection does not reset another.

Filtering, sorting, and pagination replace only one stable result wrapper:

```text
full page
├── page header                         never replaced
├── filter panel                        remains operable without HTMX
└── #collection-results                 HTMX outerHTML boundary
    ├── result count
    ├── table or empty state
    └── pagination
```

The partial response contains that wrapper and nothing from the page header.
Every HTMX link also has a valid `href`, and the updated URL can be refreshed
or shared. Templates render prepared state; filtering and sort logic remain in
forms, query helpers, and views.

## Empty states

An empty collection is a full interface state, not a blank card or a lone
sentence. Use `section.empty.empty-bordered` with:

- `empty-icon` for a quiet, relevant icon;
- `empty-title` in sentence case;
- `empty-subtitle text-secondary` explaining the next useful step;
- `empty-action` when the user can resolve the state directly.

```text
┌─ empty bordered area ────────────────────────────────────────────────┐
│                              [icon]                                  │
│                         No profiles yet                              │
│          Create the journal context for your trading decisions.     │
│                          [+ Create profile]                          │
└─────────────────────────────────────────────────────────────────────┘
```

Distinguish two cases:

- an unfiltered empty collection explains what to create and offers the same
  primary creation action as the page header;
- an empty filtered result says that nothing matches and tells the user to
  change or reset filters. It does not imply that the collection itself is
  empty and normally does not repeat the creation action.

When a collection is an HTMX target, its empty state stays inside the result
wrapper so table and empty views can replace each other without moving the
page header or filter panel.

## Forms

Simple, single-purpose forms are centered below the persistent page header:

```text
DIRECTION
Form title

              ┌─ card ─────────────────────────────────┐
              │ Label                                  │
              │ [control                           ]   │
              │ Contextual meaning or expected format  │
              │                                        │
              ├────────────────────────────────────────┤
              │                    [Cancel] [Save ...] │
              └────────────────────────────────────────┘
```

Use `row justify-content-center` and normally
`col-12 col-lg-8 col-xl-7`. A longer structured form may use a wider centered
column and several cards whose headings describe real groups, such as identity
and risk mandate.

Render ordinary fields through `tradefog/components/form_field.html` and use
Tabler controls: `form-control`, `form-select`, and `form-check-input`. Every
visible control has a concise `form-hint` connected with
`aria-describedby`. A hint explains domain meaning, consequences, an expected
format, or the next step; it does not restate the label.

Field errors appear as `invalid-feedback d-block`, and invalid controls receive
the established error border. Non-field errors appear before the fields in a
danger alert. Use active verbs and stable vocabulary for submit buttons, such
as `Create profile` or `Save changes`, rather than a generic `Submit`.

Unavailable data must not appear as an enabled empty select or editable fake
value. Disable the actual control with `disabled` and
`aria-disabled="true"`, retain Tabler's disabled appearance, and add a hint
that names the prerequisite and where it can be completed. For example, the
trade instrument selector remains disabled until a compatible instrument
exists in the shared catalog; regular users who need a new market ask a staff
member rather than creating one in the form.

## Context and responsive behavior

Page direction establishes context without repeating it in every card. Profile
pages use the profile as their parent context; shared catalog pages use the
Settings context. Keep shared catalog facts separate from a profile's journal
configuration in both wording and actions.

Layouts must remain readable at the smallest supported viewport. Header rows
may wrap, filter grids collapse to one column, forms use `col-12`, and tables
scroll within `table-responsive`. Keyboard focus is visible. Tooltips can be
reached without a mouse. Decorative icons are hidden from assistive technology;
icon-only controls have labels. Any custom animation respects
`prefers-reduced-motion`.

All visible copy is translated. English is the source language and Russian is
supported. Interface copy uses plain language, active voice, and sentence case.

## Reusable components

| Purpose | Canonical implementation |
| --- | --- |
| Direction, title, and help tooltip | `components/page_heading.html` |
| Ordinary form control and hint | `components/form_field.html` |
| Collection filter panel | `components/filter_panel.html` |
| Shared icon markup | `components/icon.html` |
| Server-side pagination footer | `journal/partials/pagination.html` |
| Sortable collection result | A collection-specific partial with one stable wrapper |
| Simple centered form | `journal/simple_form.html` where its context is sufficient |

Reuse these components before copying their markup. A specialized component is
appropriate only when semantics or interaction differ, not merely to change
spacing on one page.

## Conformance

A new or revised page conforms to this guide when:

- its page header occupies the shared header slot and remains outside cards
  and HTMX result fragments;
- direction, title, help, and the primary action are visually consistent with
  sibling sections;
- empty and filtered-empty states are intentional and actionable;
- growing collections use server-side filters, sorting, and pagination with
  refreshable URLs;
- forms use Tabler controls, contextual hints, visible validation, and a
  centered layout when they are the page's single task;
- disabled states explain how the user can satisfy their prerequisite;
- the interface remains usable without HTMX, with a keyboard, and on a narrow
  viewport.
