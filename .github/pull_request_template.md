<!--
Title format: <type>(<scope>): <description>, under 72 characters.
See .claude/pr-guidelines.md and .claude/commit-conventions.md.

Note: the subject line of the merged commit decides the next version — `feat` is
a minor bump, `fix`/`perf`/`refactor`/`chore`/`docs` a patch, `!` or
BREAKING CHANGE a major. Get it right here.
-->

## What
<!-- One-paragraph summary of the change -->

## Why
<!-- Motivation: bug, feature request, refactor reason -->

## How
<!-- Non-obvious implementation decisions. Skip what the diff already says. -->

## Testing
<!-- What you ran, and what it proved. Say plainly if a gate could not run. -->

---

- [ ] `just ci` passes — all four gates, zero warnings
- [ ] One logical change, in one commit (see `.claude/git-flow.md`)
- [ ] New crates declare `[lints] workspace = true`
- [ ] Public items have `///` docs; MSRV in `Cargo.toml` not bumped incidentally
