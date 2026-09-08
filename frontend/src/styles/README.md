# Tradefog SCSS

The application uses one dark terminal theme. Global styles are namespaced
under `.tf-app`; this is the Tradefog style prefix and prevents collisions
when the compiled SPA is embedded or extended.

## Module responsibilities

- `_tokens.scss` — semantic color, type, elevation, and radius tokens only.
- `_base.scss` — reset, document defaults, focus treatment, accessibility.
- `_components.scss` — reusable controls and generic application states.
- `_auth.scss` — authentication and entry-screen composition.
- `_shell.scss` — signed-in navigation shell and workspace cards.
- `_responsive.scss` — breakpoint-specific overrides, ordered from wide to
  narrow.

## Conventions

- Use `--tf-*` semantic tokens; do not introduce literal colors in component
  modules unless constructing a gradient or an alpha variant of a token.
- Nest selectors only one structural level beneath `.tf-app`; avoid selector
  depth that couples a component to an unrelated parent.
- Keep a component's normal, focus, hover, and disabled styles together.
- Add a new module only for a coherent feature area, then import it in
  `main.scss` before `_responsive.scss`.
