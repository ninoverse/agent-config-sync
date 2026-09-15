---
title: Releases
scope: on-demand
when: Any change that ends in a PR
---

A release tag here is a marker, not a deploy. `bump-version.yml` tags every push
to `main` whose subject is a conventional commit, and no workflow watches for the
tag: it exists so a version of this repository can be named.

- A stray push to `main` still cuts a tag, and may commit a version bump back to
  `main` on top of it.
- A workflow that deploys on the tag changes what this repository is. Change its
  `deployment` in `.agentprofile.yml` in the same PR.
