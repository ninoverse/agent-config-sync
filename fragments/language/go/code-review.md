---
title: Go code review
scope: on-demand
when: Reviewing PRs
---

Read alongside *Code review*, which holds the checks every language shares.

## What to check

### Error handling
- Every returned `error` is checked (enforced by `errcheck`) — no ignored
  errors via `_ =` in non-test code paths. Test code is exempt.
- Wrap errors with context as they propagate: `fmt.Errorf("doing x: %w", err)`
  preserves the chain for `errors.Is` / `errors.As`.
- No `panic` in normal control flow; reserve it for truly unrecoverable
  programmer errors. Prefer sentinel errors (`var ErrNotFound = errors.New(...)`)
  or typed errors (`type ValidationError struct{...}`) over string matching.

### Avoid unsafe escapes
- Avoid `unsafe` and reflection (`reflect`) unless there is no safe alternative;
  if used, justify it in one line in the PR description.
- Lean on `go vet` and the race detector (`-race`) rather than hand-rolled
  guarantees. Guard shared state with the `sync` primitives or channels.

### Public API
- Every exported identifier (`func`, `type`, `const`, `var`) has a doc comment
  that starts with the identifier's own name (`// FindByID returns …`).
- Each package has a package comment (`// Package store …`), in `doc.go` or atop
  the primary file.
- Public behavior has a runnable `Example` function (with an `// Output:` block)
  unless it is trivially obvious from the signature.

### Dependencies
- `make vuln` reports no known, reachable vulnerabilities.
- `make licenses` passes — no forbidden licenses. Module integrity is guaranteed
  by `go.sum` + the checksum database (`GOSUMDB`).
- A change that does raise the `go` directive edits `go.mod`, `.go-version`, the
  `Dockerfile` and the `go-version` input in `.github/workflows/ci.yml` together
  — a PR that moves some of those and not the rest goes red on the floor job.

### Tests
- Tests are table-driven where it fits, and `make test-race` passes.
