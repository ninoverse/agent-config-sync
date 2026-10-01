---
title: Element tests
scope: on-demand
when: Testing/Verifying
---

Every element ships two test files beside it. They run with the rest of the
suite, so the gates in *Testing instructions* cover them.

## `<name>.test.ts`, in a browser

Named `it` blocks, in this order:

| Block | Asserts |
|-------|---------|
| `registers` | `customElements.get('<prefix>-<name>')` is defined |
| `renders` | `[part~="base"]` exists in the shadow root **and** has a box: `getBoundingClientRect()` is not 0×0. Presence alone passes for a node that renders invisibly (*Element styles*). An element meant to take no space asserts the size it should have instead. The `~=` token selector matters: a base may carry more than one part. |
| `reflects <prop>` | One per reflected property: property to attribute, and attribute to property |
| `boolean attribute presence` | The bare attribute is `true`, and removing it makes the property `false` |
| `dispatches <prefix>-<event> with detail` | One per event: the shape of `detail`, `bubbles` and `composed`, and `cancelable` for a dismissal. The listener sits on `document`, which proves the event left the shadow root. |
| `projects <slot> slot` | The default slot and each named one: `assignedElements()` holds the projected node |
| `submits its value and resets` | Form controls only: `new FormData(form).get(name)` has the value, and `form.reset()` restores the default |
| `exposes roles` | The `role` and `aria-*` attributes on the base node |

Fixtures come from Lit's own `render()`, into a host appended to
`document.body` and emptied after each test, as the `/new-element` template
does. A testing library on top would be one more dependency for nothing.

## `<name>.ssr.test.ts`, in Node

The module imports in Node without touching `window` or `document`, and
`render()` from `@lit-labs/ssr` produces declarative shadow DOM: the output
contains `<template shadowroot`, `part="base"` and the slotted text.

## Rules

- No snapshots of whole shadow markup, which break on every harmless change.
  Assert parts and attributes.
- `renders` measures layout, so the browser tests run in a real browser, not in
  a DOM emulation such as jsdom.
