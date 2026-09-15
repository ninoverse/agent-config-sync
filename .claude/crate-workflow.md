# Crate Workflow

The exact procedure for adding or modifying a single crate in this Cargo
workspace. Follow every step in order; do not skip or reorder.

---

## Pre-flight

Before writing any code:

1. **Ask for confirmation.** State which crate you are about to add and what it
   will contain. Wait for explicit approval. Do not start on your own initiative.

2. **Check if the crate already exists:**
   ```bash
   ls crates/<name>/Cargo.toml 2>/dev/null && echo EXISTS || echo MISSING
   ```
   If it exists, report the finding and ask: skip / overwrite / modify.
   Never silently overwrite.

---

## 9-step checklist (one crate, one commit)

Complete all nine steps before committing. Never commit a partial crate.

### 1. Scaffold the crate

```bash
cargo new --lib crates/<name>     # use --bin for an executable instead
```

Crate directory naming: `kebab-case` (e.g. `crates/data-store`). The crate's
identifier in code becomes `snake_case` (`use data_store::…`).

### 2. `crates/<name>/Cargo.toml`

Inherit shared metadata from the workspace:

```toml
[package]
name = "<name>"
version = "0.1.0"
edition.workspace = true
license.workspace = true
repository.workspace = true
rust-version.workspace = true

[dependencies]
# Shared deps come from the workspace:
# serde = { workspace = true }

[lints]
workspace = true
```

The `[lints]` table is **not** optional. Without it the crate silently opts out
of the workspace lints in `Cargo.toml` and `-D warnings` will not catch a
missing doc comment or an `unwrap()` in a non-test path.

### 3. `crates/<name>/src/lib.rs` (or `main.rs`)

- Public API surface only. Implementation lives in submodules.
- Every `pub` item gets a `///` doc comment.
- Crate-level docs go in a `//!` block at the top of the file.

### 4. Module split

Any item > ~150 LOC moves to its own file: `crates/<name>/src/<module>.rs`,
declared with `mod <module>;`. Filenames are `snake_case.rs`.

### 5. Unit tests

Inline at the bottom of the file under test:

```rust
#[cfg(test)]
mod tests {
    // Test code is exempt from the unwrap/expect ban; see .claude/code-review.md.
    #![allow(clippy::unwrap_used, clippy::expect_used)]

    use super::*;

    #[test]
    fn computes_expected_result() {
        assert_eq!(do_thing(2), 4);
    }
}
```

The inner `#![allow(...)]` is what makes the exemption real. `unwrap_used` and
`expect_used` are set workspace-wide and fire in test targets too, so without it
a `.unwrap()` in a test fails the clippy gate.

### 6. Integration tests + doc tests

- Integration tests: `crates/<name>/tests/<feature>.rs`. Each file compiles as
  a separate binary against the crate's public API.
- Doc tests: every public function gets a runnable example in its `///` doc
  comment unless the behavior is trivially obvious from the signature.

### 7. Workspace wiring

The workspace `Cargo.toml` already globs `crates/*`, so new crates are picked
up automatically. If this crate depends on another workspace crate, add it
with a path dependency:

```toml
[dependencies]
other-crate = { path = "../other-crate" }
```

### 8. Verification gate

All four gates must pass, with zero warnings, before committing:

```bash
just ci
```

### 9. Commit + push + hand over the PR

```
feat(<crate>): add <name> crate
```

One crate per commit, one commit per branch. Never batch multiple crates.

- Push the branch: `git push -u origin feat/<name>`.
- Output the PR title and description (`.claude/pr-guidelines.md`). Do not open
  the PR — the user does that.
- **Stop.** Wait for the merge, then start the next crate from a fresh `main`.

The full loop is in `.claude/git-flow.md`.
