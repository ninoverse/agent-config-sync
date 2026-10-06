---
title: Route sequencing
scope: on-demand
when: Deciding what to build next / branching strategy
---

Routes are the unit of work here: the app holds many, and each PR builds one.
This adds to *Execution order*; it does not replace it.

- One route per PR, built with *Adding a route*: its page, the segment files it
  needs, its components and their tests.
- What several routes share, such as a layout, a component or a data function,
  lands with the first route that needs it, in that route's PR, never ahead of
  it.
- A change to the root layout is a PR of its own, since every route renders
  inside it.
- A new major version of Next.js comes in a PR of its own, and nothing else
  rides along. It follows the upgrade guide for that version, read from the
  newly installed `node_modules/next/dist/docs/01-app/02-guides/upgrading/`,
  with the codemods the guide names.
