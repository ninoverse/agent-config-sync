---
title: Code review
scope: on-demand
when: Reviewing PRs
---

The checks every change gets, whatever the language. The language's own review
rules — error handling, unsafe code, public API docs — load for the same trigger
and are read alongside these.

## What to check

### Gates
- `{{ gate_command }}` passes — {{ gates }}, {{ gates_clean }}.
- No {{ lint_suppression }} added without a justifying comment.

### Dependencies
- New dependencies have a one-line justification in the PR description.
- The {{ version_floor }} is not raised unless the change explicitly intends to.

### Tests
- New behavior is covered by at least one test.
