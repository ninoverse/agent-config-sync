---
title: Next.js documentation
scope: always
---

The installed Next.js may not be the one you learned: its APIs, file
conventions and defaults change between releases, minor ones included. Before
writing or changing Next.js code, read the matching guide in
`node_modules/next/dist/docs/`, which ships with the installed version. The App
Router's are under `01-app/`: getting started, guides, and a reference for
every file convention, function and config option. Where a guide and what you
remember disagree, the guide wins, and so do its deprecation notices.

Keep `agentRules: false` in `next.config.ts`. This section replaces the block
`next dev` would otherwise write into AGENTS.md.
