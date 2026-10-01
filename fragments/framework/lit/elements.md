---
title: Elements
scope: paths
paths:
  - "src/elements/**"
---

## Shape

- One folder per element, `src/elements/<name>/`, where `<name>` is the
  element's name in kebab-case. Its tag is `<prefix>-<name>`, with the prefix
  every element in this repository shares, and its class is the tag in
  PascalCase.
- `<name>.ts` declares the class, which `extends LitElement`, registers it with
  `@customElement('<prefix>-<name>')`, and adds the tag to
  `HTMLElementTagNameMap`.
- Decorators are the TC39 standard ones, with `accessor`:
  `@property() accessor variant = 'primary'`. Never enable
  `experimentalDecorators`.
- A member that overrides `LitElement`'s says so: `static override styles`,
  `override render()`, `override connectedCallback()`.
- An element renders another by its tag, importing that element's module for
  its side effect (`import '../button/button.js'`). Never import a class to
  construct it.

## Properties

- Reflect every attribute that CSS selects on, such as
  `:host([variant='primary'])` or `:host([open])`. Never reflect data.
- Booleans follow HTML: the attribute present is `true`, absent is `false`, and
  `disabled="false"` is `true`. Never write a converter that parses `"false"`.
- Arrays and objects are properties only, never serialized to an attribute:
  `@property({ type: Array, attribute: false })`.
- A property whose name has several words names its attribute:
  `@property({ type: Boolean, reflect: true, attribute: 'as-icon' })`.
- The element owns its state. `value`, `checked` or `open` is the current state;
  setting it from outside replaces it, and user interaction updates it and
  dispatches the matching event.
- Every property has a one-line JSDoc with `@default`, and the class JSDoc
  lists `@tag`, `@slot`, `@csspart` and `@fires`. Documentation tools, such as
  a custom elements manifest, are built from these comments.

## Lifecycle and server rendering

- A listener on `document` or `window` is added in `connectedCallback` with the
  `signal` of a new `AbortController`, which `disconnectedCallback` aborts.
- An outside click is detected with `event.composedPath().includes(this)`, never
  with `event.target`, which the shadow boundary retargets to the host.
- Nothing touches `window`, `document`, `customElements` or `matchMedia` at
  module scope or in the constructor. Browser-only work in `connectedCallback`
  starts with `if (isServer) return;`, with `isServer` from `lit`.
- `render()` depends on properties and state alone: no `Math.random()`, no
  `Date.now()`, no measured sizes in the first render.
- The element never changes its light DOM: it doesn't move or append the
  consumer's nodes, or read their `textContent` to render it again. Content
  reaches the shadow root through a `<slot>`.

## Events

- A callback is never a function property. It is a `CustomEvent` named
  `<prefix>-<event>`, dispatched through the helper in
  `src/elements/shared/events.ts`, which sets `bubbles` and `composed` so the
  event leaves the shadow root.
- `detail` is always an object, keyed by what it carries: `{ value }`,
  `{ open }`.
- A dismissal, such as close or cancel, is `cancelable`: the element reads what
  `dispatchEvent` returns and stays open when a listener called
  `preventDefault()`.
- A text input follows the native pair: `<prefix>-input` on every keystroke,
  `<prefix>-change` when the value is committed, on blur or Enter. Checkboxes,
  selects and the like fire `<prefix>-change` only.
- Each event's `detail` type is exported as `<Name><Event>Detail`, and the class
  JSDoc lists the event with `@fires`.
- A native event that already leaves the shadow root, such as `click` or
  `input`, is not dispatched again. One that doesn't and that consumers need,
  such as `load` or an inner control's `change`, is dispatched again as
  `<prefix>-<event>`.

## Slots or properties

- Rich content that appears once is a named slot: a title is
  `<slot name="title">`. A string property of the same name stays as the slot's
  fallback only where the content is usually plain text.
- A list's items are strings in an array property. Each rendered item has a slot
  of its own, such as `<slot name="label-<value>">`, with the string as its
  fallback.

## What is public

An element's public surface is everything a consumer can rely on without reading
its source:

- the tag name, and the module path that defines it;
- attributes and properties: names, types, defaults, and which reflect;
- events: names, the shape of `detail`, and whether they bubble, cross the
  shadow boundary or can be cancelled;
- slots and parts, by name;
- the CSS custom properties the element reads;
- form behaviour: form association, value and validity.
