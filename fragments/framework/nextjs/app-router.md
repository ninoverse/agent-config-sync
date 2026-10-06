---
title: App Router
scope: paths
paths:
  - "app/**"
  - "src/app/**"
---

## Server and Client Components

- Layouts and pages are Server Components unless a file says otherwise, and
  they stay that way: they fetch data, read secrets, and send the browser no
  JavaScript of their own.
- `'use client'` goes at the top of a file, above its imports, and marks a
  boundary: everything that file imports joins the client bundle. Put it on the
  smallest component that needs state, effects, event handlers or browser APIs,
  never on a layout or a page to make one hook work.
- Props that cross into a Client Component are serializable: data, not
  functions or class instances, Server Functions excepted. They carry what the
  component renders, not whole records.
- A Client Component renders a Server Component only through `children` or
  another prop. One it imports becomes a Client Component itself.
- A Client Component is never `async`. It receives a promise from a Server
  Component and unwraps it with React's `use`.
- A library component that uses state or the browser, and has no
  `'use client'` of its own, is wrapped in a Client Component of yours.
- A context provider is a Client Component that takes `children`, rendered as
  deep in the tree as it can be.

## Data

- Data is fetched in Server Components, with `await`, near where it is used.
  Not in a Client Component's `useEffect` when a Server Component could load it.
- Request-time APIs are async: `params`, `searchParams`, `cookies()`,
  `headers()` and `draftMode()` are awaited. Pages, layouts and route handlers
  are typed with the generated `PageProps<'/route'>`, `LayoutProps<'/route'>`
  and `RouteContext<'/route'>`, which need no import.
- A module that reads secrets or the database starts with
  `import 'server-only'`, so importing it into client code fails the build.
- Only `NEXT_PUBLIC_` variables reach the browser, inlined at build time, so a
  secret never carries that prefix.
- Slow data sits inside `<Suspense>`, or under the segment's `loading.tsx`, so
  the rest of the page streams first.
- How data is cached depends on `cacheComponents` in `next.config.ts`. Read the
  caching guide for the model in use before adding `'use cache'` or changing
  revalidation.

## Mutations

- A mutation is a Server Function, marked `'use server'`, never a side effect
  of rendering.
- Every Server Function is reachable by a direct POST, whatever page calls it.
  It validates its input, checks authentication and authorization itself, and
  returns only what the client needs.
- An expected failure, such as invalid input, is returned as a value and shown
  through `useActionState`, not thrown.

## Pages

- A page's title and description are its `metadata` export or
  `generateMetadata`, in a Server Component, never `<title>` or `<meta>` tags
  written by hand.
- Internal links are `next/link`'s `<Link>`, images `next/image`'s `<Image>`,
  and web fonts `next/font`.
- `error.tsx` is a Client Component and recovers with `retry()`. `notFound()`
  renders the nearest `not-found.tsx`.
- Global CSS holds only what is truly global, and is imported in the root
  layout. A component's own styles are a CSS Module beside it.
