---
title: Template repository
scope: always
---

This repository is a GitHub template: new projects start as a copy of it, and
every copy inherits everything here.

- Keep the example code minimal. It demonstrates the conventions and keeps the
  gates green on a fresh copy; it holds no real business logic.
- Where the template ships placeholder {{ units }}, they exist because the
  gates fail on an empty {{ unit_container }} and the `Dockerfile` needs a
  binary to build. Remove a placeholder only once a real {{ unit }} covers its
  role, as a change of its own, and point the `Dockerfile` at the real binary in
  that change.
- A project created from this template removes `template` from `concerns` in its
  `.agentprofile.yml`.
