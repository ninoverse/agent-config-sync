---
title: Next.js tests
scope: on-demand
when: Testing/Verifying
---

What *Testing instructions* runs, as it applies to the app. Component tests run
in Vitest's browser mode, in Chromium through Playwright, rather than in a DOM
emulation such as jsdom: layout, focus and custom elements behave there as they
do for a visitor.

## What gets which test

| Code | Test |
|------|------|
| A Client Component | `<name>.test.tsx` beside it, rendered with `render` from `vitest-browser-react` |
| A Server Component that is not `async` | The same, rendered as any component is |
| An `async` Server Component, a Server Function, a Route Handler | None of its own: Vitest renders no `async` component and serves no request. Keep it thin, and test the logic it calls. |
| That logic | `<name>.test.ts` beside its module, called with plain arguments |

## Rules

- Logic under test lives in a module that imports neither `server-only` nor a
  request-time API such as `cookies()`. Outside Next.js's build, a module that
  imports `server-only` can't be imported, so its test fails before it runs. The
  component, Server Function or Route Handler reads the request and the secrets,
  and passes plain values down.
- Find elements by role, label or their whole text. A locator matches the whole
  text, case included, unless `browser.locators.exact` is off, so
  `getByText('Edit')` finds nothing in "Edit the page". Use `{ exact: false }` to
  match part of a text.
- Assert what a visitor perceives, never a snapshot of the markup.
- The build checks pages as well: `pnpm build` prerenders every static route,
  so a page that throws while rendering fails the build gate. Read its route
  table too: a route that turned dynamic (ƒ) without meaning to is a bug.
