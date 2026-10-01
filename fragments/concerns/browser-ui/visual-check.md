---
title: Visual check
scope: on-demand
when: Opening PRs
---

A PR that changes what a page renders carries a visual-check record. An agent
can't attach an image to a PR description, so the images go to the reviewer in
the session, and the PR keeps the record of what was compared.

- Before opening the PR, capture each affected section with *Taking a
  screenshot*, and show the images to the reviewer in the session.
- Write the captures outside the repository, so they never land on `main`.
- The description carries the record, after *Testing*. For each capture: the
  page and section, the viewport and scale, the theme settings in effect,
  whether web fonts loaded, and the entry that took it. Then the verdict, and
  who gave it.
- If the verdict is still pending when the PR opens, open it as a draft, and
  mark it ready once the reviewer approves.

```markdown
## Visual check

- `examples/index.html` · Badge · 1000 × 900 at 2× · light theme · web fonts loaded · playwright
- `src/App.tsx` · Badge · same settings

Verdict: the new Badge matches the old one. Approved in the session by <reviewer>, <date>.
```
