---
title: Element review
scope: on-demand
when: Reviewing PRs
---

For a PR that adds or changes an element, alongside *Code review*.

## Shape (*Elements*)

- The folder holds `<name>.ts`, `<name>.styles.ts`, `<name>.test.ts` and
  `<name>.ssr.test.ts`; the tag and class follow *Element files*, and the tag is
  in `HTMLElementTagNameMap`
- Standard decorators with `accessor`, and `override` on every member that
  overrides `LitElement`'s
- Attributes CSS selects on reflect, data is `attribute: false`, and multi-word
  properties name their attribute
- Booleans use presence: no converter parsing `"false"`
- Every property has a JSDoc line with `@default`; the class lists `@tag`,
  `@slot`, `@csspart` and `@fires`

## Styles (*Element styles*)

- `:host` has a `display`, and so does every inner node with a size
- No selector outside the root; the consumer's children only through
  `::slotted()`
- Colours, radii, shadows and spacing only through custom properties
- `part="base"` on the root node; no `z-index` on an overlay

## Behaviour

- Events: through the shared helper, an object `detail`, dismissals cancelable
  and honoured, text inputs firing both input and change
- `connectedCallback` returns early under `isServer`; listeners on `document`
  and `window` hang off an `AbortController` aborted on disconnect
- Outside clicks through `composedPath()`; `render()` deterministic; the light
  DOM never changed
- Form controls (*Forms and overlays*): `ElementInternals`, value and validity,
  the reset and disabled callbacks, `delegatesFocus`
- Overlays: a `<dialog>` or the `popover` attribute, and focus given back on
  close

## Tests and the description

- The blocks *Element tests* lists, in its order, and the server-render test
- The description carries the element's API table (*Element API table*), and a
  change to anything *Elements* lists as public is called out
