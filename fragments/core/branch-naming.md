---
title: Branch naming
scope: on-demand
when: Creating branches
---

## Format

```
<type>/<short-description>
```

- All lowercase, words separated by hyphens
- Keep the description short (2–5 words)
- No ticket numbers unless a tracking system is in use

## Types

| Prefix | When to use |
|--------|-------------|
| `feat/` | New feature |
| `fix/` | Bug fix |
| `refactor/` | Refactor with no behavior change |
| `chore/` | Tooling, deps, CI, config |
| `docs/` | Documentation only |
| `wip/` | Exploratory / work-in-progress (not for PRs) |

## Examples

```
feat/user-profile-page
fix/login-redirect-loop
refactor/date-format-utils
chore/upgrade-linter
docs/update-setup-guide
wip/spike-new-api
```

## Rules

- Branch off an up-to-date `main`, never off another branch — see *Git flow*.
- Delete branches after merging.
- Never commit directly to `main`.
