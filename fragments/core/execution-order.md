---
title: Execution order
scope: on-demand
when: Deciding what to build next / branching strategy
---

Defines the branch / PR structure for work in this {{ unit_container }}.

---

## Branching and PR strategy

See *Branch naming* for the branch name format.

| Work type | Branch prefix | One PR per |
|-----------|--------------|-----------|
| Foundation scaffold | `chore/` | scaffold step |
| Toolchain / config bump | `chore/` | bump |
| Group of {{ units }} | `feat/` | {{ unit }} — a group is a *sequence* of PRs, not one PR |
| Single isolated {{ unit }} | `feat/` | {{ unit }} |
| Rename / refactor | `refactor/` | logical rename unit |
| Docs / rules | `docs/` | change |

**The loop is defined in *Git flow*** — branch from `main`, one
commit, hand the PR to the user, wait for the merge, repeat. No stacked PRs, and
every PR must leave `main` green on its own.

---

## Within each group

- Build **one {{ unit }} at a time**, each on its own branch and its own PR.
- Follow the 9-step checklist in *Adding a {{ unit }}* for each.
- Wait for the {{ unit }}'s PR to be merged before cutting the branch for the next.
- Order the {{ units }} so each one compiles against what is already on `main`. A
  {{ unit }} that needs a not-yet-merged sibling belongs later in the sequence.
- Existing {{ units }} in scope get an **audit-pass** (lint + tests + a read-through);
  only commit if a real defect is found.

## Audit-pass checklist (existing {{ units }})

1. Read the {{ unit }} — check for outdated deps, missing doc comments on the
   public API, and the error-handling shortcuts *Code review* bans in non-test
   paths.
2. Run `{{ unit_lint_command }}` and `{{ unit_test_command }}`.
3. Surface anything broken. Only commit if a fix is needed — and give the fix its
   own branch and PR rather than folding it into unrelated work.
