# Code Review Guidelines

## What to check

### Lint and format
- `just fmt-check` passes — no formatting drift.
- `just lint` passes with zero `#[allow(...)]` attributes added without a
  justifying comment.
- Every new crate's `Cargo.toml` has `[lints] workspace = true`. Without it the
  crate opts out of the workspace lints and the gate cannot catch anything.

### Error handling
- No `.unwrap()` or `.expect()` in non-test code paths. Use `?` with a typed
  error (`thiserror`, `anyhow`, or a hand-rolled enum). Test code, build
  scripts, and examples are exempt.
- Errors flow through `Result<T, E>` — no `panic!` / `unreachable!` /
  `todo!` in normal control flow.
- New error variants are documented in their enum's `///` comment.

### Unsafe code
- `unsafe_code` is denied workspace-wide. A crate that genuinely needs it opts
  in with a crate-level `#![allow(unsafe_code)]` carrying a comment that says
  why — which makes the exception greppable and reviewable.
- Every `unsafe` block has a `// SAFETY: …` comment explaining the invariants
  the caller relies on.
- Prefer safe abstractions; `unsafe` requires a one-line justification in the
  PR description.

### Public API
- Every `pub` item (`fn`, `struct`, `enum`, `trait`, `mod`, `const`) has a
  `///` doc comment.
- Public functions have a runnable doc-test example unless behavior is trivially
  obvious from the signature.
- Breaking changes to a published crate bump the major version in `Cargo.toml`.

### Dependencies
- New dependencies have a one-line justification in the PR description.
- `just deny` passes — licenses allowed, no known advisories,
  no unknown sources.
- MSRV in `clippy.toml` and `[workspace.package].rust-version` not bumped
  unless the change explicitly intends to.

### Tests
- New behavior is covered by at least one unit or integration test.
- `just test` passes — unit, integration and doc-tests.
