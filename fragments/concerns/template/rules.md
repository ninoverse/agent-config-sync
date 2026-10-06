---
title: Template repository
scope: always
---

This repository is a GitHub template: new projects start as a copy of it, and
every copy inherits everything here.

- Keep the example code minimal. It demonstrates the conventions and keeps the
  gates green on a fresh copy; it holds no real business logic.
- Where the template ships placeholder code, it is there because the gates
  fail without it, and because what the template builds, such as the binary a
  `Dockerfile` packages, needs something to build. Remove a placeholder only
  once real code covers its role, as a change of its own, and in that change
  point whatever names the placeholder at the real code.
- A project created from this template removes `template` from `concerns` in its
  `.agentprofile.yml`.
