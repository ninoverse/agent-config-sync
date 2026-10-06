---
title: App files
scope: on-demand
when: Creating new files
---

An app has no `src/index.ts`: its routes are its entry points, and the folders
under `app/` are its URLs. This takes the place of the per-package layout in
*Directories and file naming*, whose naming conventions still hold.

## Layout

| Path | Contents |
|------|----------|
| `app/` | The App Router: one folder per URL segment. `src/app/` where the app keeps its code under `src/`. |
| `app/layout.tsx` | The root layout, which every route renders inside: `<html>`, `<body>`, global CSS and fonts |
| `app/<segment>/_components/` | Components only that segment uses. A leading underscore keeps a folder out of routing. |
| `public/` | Static files, served from `/` as they are |
| `proxy.ts` | Code that runs before a request reaches its route. It was `middleware.ts` before Next.js 16. |
| `next.config.ts` | Next.js's configuration |
| `next-env.d.ts`, `.next/` | Written by Next.js, and git-ignored |

## Special files

Inside a segment, these names belong to Next.js, so nothing else takes them:

| File | Role |
|------|------|
| `page.tsx` | The segment's UI, and what makes it a route |
| `layout.tsx` | UI the segment and its children share, kept across navigation |
| `loading.tsx` | The fallback shown while the segment loads |
| `error.tsx` | The segment's error boundary, a Client Component |
| `not-found.tsx` | What `notFound()` renders |
| `route.ts` | A Route Handler, exporting `GET`, `POST` and the other methods. Never beside a `page.tsx`. |
| `template.tsx`, `default.tsx`, `global-error.tsx` | Rarer: read their reference before adding one |

## Segments

| Folder | URL |
|--------|-----|
| `about/` | `/about` |
| `[slug]/` | One dynamic segment, read from `params` |
| `[...slug]/`, `[[...slug]]/` | Catch-all, and optional catch-all |
| `(group)/` | Nothing: a route group organizes routes and shares a layout |
| `_private/` | Nothing: never a route |

## Naming

| Item | Convention | Example |
|------|------------|---------|
| Segment folders | lowercase `kebab-case`, since they are the URL | `app/order-history/` |
| Component files | `kebab-case`, after the component | `user-card.tsx` |
| Components | `PascalCase` | `UserCard` |
| Tests | the file's name plus `.test` | `user-card.test.tsx` |
| CSS Modules | the component's file name plus `.module.css` | `user-card.module.css` |
