---
title: Element API table
scope: on-demand
when: Opening PRs
---

A PR that adds an element, or changes any of what *Elements* lists as public,
carries the element's API table in its description, after *Testing*. One row per
property, slot, event or part, with `—` where a column doesn't apply:

```markdown
## API

| Property / attribute | Slot | Event (detail) | Part |
|----------------------|------|----------------|------|
| `variant`: `'primary' \| 'secondary'`, default `'primary'`, reflected | — | — | — |
| — | default: the label | — | `base` |
| — | — | `my-change` (`{ value: string }`) | — |
```

Below it, one line each for what the table has no column for: whether the
element is form-associated, and the CSS custom properties it reads.

For a change to an existing element, the table lists what the PR adds, changes
or removes, and says which.
