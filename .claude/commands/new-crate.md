---
description: Add a crate to the workspace following the 9-step crate workflow
argument-hint: <crate-name> [one-line description of what it does]
---

Add a new crate named `$1` to this workspace.

Read `.claude/crate-workflow.md` in full before doing anything, then follow all
nine steps in order. Do not skip, reorder, or batch them.

Full request: $ARGUMENTS

The pre-flight rules in that file still apply:

1. State what the crate will contain and **wait for explicit approval** before
   writing any code.
2. Check whether `crates/$1/Cargo.toml` already exists. If it does, stop and ask
   whether to skip, overwrite, or modify. Never silently overwrite.

Points that are easy to get wrong, so verify each one before committing:

- `[lints] workspace = true` in the crate manifest. Without it the crate opts
  out of the workspace lints and the clippy gate cannot catch anything.
- Package keys inherit from the workspace: `edition.workspace = true`, and the
  same for `license`, `repository` and `rust-version`.
- Every `pub` item has a `///` doc comment, and public functions have a runnable
  doc-test — `missing_docs` is a workspace lint and the gate runs with
  `-D warnings`.
- The test module carries `#![allow(clippy::unwrap_used, clippy::expect_used)]`,
  otherwise an `.unwrap()` in a test fails the clippy gate.
- `just ci` passes before you commit.

Finish at step 9: one commit, push the branch, output the PR title and
description, then stop. Do not open the PR — see `.claude/git-flow.md`.
