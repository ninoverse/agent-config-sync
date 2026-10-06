---
title: Next.js review
scope: on-demand
when: Reviewing PRs
---

For a PR that changes the app, alongside *Code review* and *TypeScript code
review*.

## The boundary (*App Router*)

- `'use client'` sits on the smallest interactive component, never on a layout
  or a page for one hook
- Props into a Client Component are serializable and carry only what it renders
- No Client Component is `async`
- Modules that read secrets or the database import `'server-only'`, and no
  secret is named `NEXT_PUBLIC_`

## Requests and mutations

- `params`, `searchParams`, `cookies()` and `headers()` are awaited, and pages
  are typed with `PageProps<'/route'>`
- A `[param]` folder is user input: `params` and `searchParams` are validated
  before use
- Every Server Function validates its input, checks authentication and
  authorization itself, and returns only what the client needs
- Nothing mutates while rendering
- A change to `proxy.ts` or a `route.ts` gets a second read: it runs on every
  request it matches

## Pages

- Metadata through `metadata` or `generateMetadata`; links through `<Link>`,
  images through `<Image>`
- Slow data inside `<Suspense>` or under a `loading.tsx`; `error.tsx` a Client
  Component that recovers with `retry()`
- The description carries the route table (*Route table*), and a route that
  became dynamic says why
