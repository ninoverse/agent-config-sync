---
title: Commit message guidelines
scope: on-demand
when: Committing code
---

Follow the [Conventional Commits](https://www.conventionalcommits.org/) specification.

## Format

```
<type>(<scope>): <description>

[optional body]
```

- Subject line: max 72 characters, lowercase, no trailing period
- Use imperative mood: "add feature" not "added feature"
- Body: wrap at 72 characters, explain *why* not *what*

## Types

| Type | When to use |
|------|-------------|
| `feat` | New feature or user-visible behaviour |
| `fix` | Bug fix |
| `refactor` | Code change with no behaviour change |
| `style` | Formatting, whitespace — no logic change |
| `docs` | Documentation only |
| `chore` | Build scripts, deps, tooling, CI |
| `perf` | Performance improvement |
| `revert` | Reverts a previous commit |

Append `!` after the type for breaking changes: `feat!: {{ breaking_change_example }}`.

## Scopes (optional but recommended)

Use the {{ unit }} name or layer being changed: `<{{ unit }}-name>`, `{{ unit_container }}`, `ci`, `deps`, `config`.

## Examples

```
feat(store): add batch insert API
fix(httpclient): retry budget leak under timeout
refactor({{ unit_container }}): move shared error type into an errors {{ unit }}
chore(deps): bump {{ dependency_bump_example }}
docs: document the {{ version_floor }} policy
feat!: {{ breaking_change_example }}
```

## The subject picks the release

`bump-version.yml` reads the commit that lands on `main` and releases
accordingly:

| Commit | Release |
|--------|---------|
| `!` after the type or scope, or `BREAKING CHANGE` anywhere in the message | major |
| `feat` | minor |
| `fix`, `perf`, `refactor`, `revert`, `style`, `chore`, `docs` | patch |
| anything else — `test`, `build`, `ci`, a merge commit | none |

- `BREAKING CHANGE` counts wherever it appears, body included. A squash commit
  whose description merely mentions the phrase cuts a major release; write it
  only when the change breaks something.
- A scope is lowercase letters, digits, `-` and `_`. `feat(API):` or
  `fix(v1.2):` matches no type, and the release is silently skipped.

## What to avoid

- Vague messages: `fix stuff`, `update`, `wip`
- Mixing unrelated changes in one commit
- Committing secrets or credentials (they are gitignored for a reason)
