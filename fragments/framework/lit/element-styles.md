---
title: Element styles
scope: paths
paths:
  - "src/elements/**/*.styles.ts"
---

- An element's CSS lives in `<name>.styles.ts`, as one `css` tagged template
  exported as `styles`, and reaches the element through
  `static override styles`. No `.css` files, no external stylesheets, and no
  `unsafeCSS` built from strings.
- `:host` gets a `display`, first: a custom element is `inline` until told
  otherwise.
- So does every inner node that CSS gives a size. An inline node ignores
  `width` and `height`, so a `<span>` styled `width: 100%; height: 100%`
  renders 0×0 and the element is invisible, while lint, the build and a test
  that only checks the node exists all pass.
- Parts are public API. The root node carries `part="base"`, and every node a
  consumer may need to style carries a part named for its role, such as `label`,
  `icon`, `panel` or `item`. The class JSDoc lists each with `@csspart`.
- Nothing selects outside the shadow root: no `:host-context()`, no selector on
  an ancestor's attribute, no descendant selector across element boundaries.
  The consumer's children are reached only through `::slotted()`.
- Colours, radii, shadows and spacing come only from CSS custom properties, the
  design tokens, and sizes are computed from them. A hook one element adds for
  theming is read as `var(--<name>-<property>, <fallback>)`.
- Motion stops under `@media (prefers-reduced-motion: reduce)`, in the same
  `css` template as the animation.
- Overlays never use `z-index`: the top layer orders them. A `0` or `1` between
  nodes inside one shadow root is fine.
- A value that differs per instance is set on the host with
  `this.style.setProperty('--<property>', …)`, or on an inner node with
  `styleMap`.
