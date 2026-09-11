# Translation dictionaries

Keep translations in `locales/en` and `locales/ru`, grouped by area.
Both languages use the same file names, message keys and interpolation
parameters. Modules export their existing top-level namespaces; file names
do not add another namespace.

- `common`: shared actions, generic states and pagination.
- `shell`: navigation, dashboard, page descriptions and workspace empty states.
- `auth`, `catalog`, `venues`, `profiles`, `trades`, `market`, `analytics`:
  translations belonging to those areas.

`messages.ts` assembles dictionaries through explicit static imports.
`index.ts` configures Vue I18n and language switching. Do not put translation
text in either file or introduce feature-local dictionaries.

Preserve semantic keys when moving text. Translate complete sentences with
parameters, and only share keys when their meaning is genuinely shared.
The i18n test checks key and parameter parity between languages.
