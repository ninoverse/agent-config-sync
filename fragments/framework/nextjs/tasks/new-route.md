---
name: new-route
title: Adding a route
when: Adding or modifying a route
description: Add a route following the 6-step route workflow
argument-hint: "<url> [one-line description of the page]"
---

The exact procedure for adding or modifying a single route. Follow every step
in order; do not skip or reorder.

The route to add: $ARGUMENTS

---

## Pre-flight

Before writing any code:

1. **Ask for confirmation.** State the URL you are about to add and what the
   page is for. Wait for explicit approval. Do not start on your own initiative.

2. **Check whether it exists:**
   ```bash
   ls app/<route>/page.tsx src/app/<route>/page.tsx 2>/dev/null && echo EXISTS || echo MISSING
   ```
   If it exists, report what is there and ask: skip / overwrite / modify. Never
   silently overwrite. This is also how an interrupted run resumes: modify, from
   the first step whose file is missing.

3. **The plan.** Say which parts render on the server and which need
   `'use client'`, where the page's data comes from, which segment files it
   needs, and how the build should render it, as one of the symbols *Route
   table* lists. Wait for approval; if the request brought an approved plan, use
   that one. The plan is the contract for every step below.

Then read *App Router*, and the reference for each special file the plan names,
under `node_modules/next/dist/docs/01-app/03-api-reference/03-file-conventions/`.
*App Router* loads on its own once a file under `app/` is read, which is too
late for the first file this task writes.

---

## 6-step checklist (one route)

The templates are in `.agents/new-route/`. In each, replace `<url>` with the
route's URL pattern, such as `/blog/[slug]`, `<Title>` with the page's title,
and `<Name>` and `<name>` with the PascalCase and kebab-case name of the page
or component. Where the app keeps its code under `src/`, every `app/` below is
`src/app/`. The templates show one of each kind of code; delete whatever the
plan doesn't call for.

### 1. The page

Copy `page.tsx.tpl` to `app/<route>/page.tsx`, where `<route>` is the URL's
path below `/`. It is a Server Component, with its `metadata`. A dynamic segment
or data makes it `async`, as the template's comment says.

### 2. The segment files the plan names

`error.tsx` from `error.tsx.tpl` where the page can fail at request time,
`loading.tsx` where it awaits slow data, and `not-found.tsx` where it calls
`notFound()`. None of them by default.

### 3. Client Components

Copy `component.tsx.tpl` to `app/<route>/_components/<name>.tsx` for each
interactive part. Its props are serializable, and only what it renders.

### 4. Tests

Copy `component.test.tsx.tpl` beside each Client Component, as
`<name>.test.tsx`. The logic the page's data goes through gets a `.test.ts`
beside its module, as *Next.js tests* says.

### 5. Verification gate

If `.agents/new-route.local.md` exists, follow it now, before the gate. It
holds the steps this repository adds to this checklist, such as the navigation
a new page appears in; it is written by hand, and `agentcfg` leaves it alone.

Then {{ gates }} must pass, with {{ gates_clean }}, before committing:

```bash
{{ gate_command }}
```

The build's route table then shows how the route renders. It matches the plan.

### 6. Commit, then hand the PR over

```
feat(<scope>): add the <url> page
```

Commit and hand the PR over as *Git flow* and *PR instructions* say, with the
route's rows from *Route table* in its description.

---

## Before committing

Points that are easy to get wrong, so verify each one:

- `'use client'` is on the components the plan named and nowhere else, never on
  the page.
- Every request-time API is awaited, and a page with a dynamic segment takes
  `PageProps<'<url>'>`.
- No secret reaches a Client Component, through its props or `NEXT_PUBLIC_`.
- The build renders the route the way the plan said.
- `.agents/new-route.local.md` was followed, if it exists.
- `{{ gate_command }}` passes before you commit.
