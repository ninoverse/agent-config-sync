One source of truth for the coding-agent instructions used across the ninoverse
repositories: rules are written once here as single-purpose fragments under
`fragments/`, and the `agentcfg` binary in `crates/` composes them per repository
from that repository's `.agentprofile.yml`.

This repository is one of those repositories. Everything below the marker is
composed from the release pinned in its own `.agentprofile.yml`, not from the
working tree — so editing a fragment changes these files only once it ships in a
release and the pin moves. `docs/fragment-authoring.md` says how to write one,
and `/new-value` is the checklist for adding a value to an axis.

<!-- agentcfg:start -->
<!-- language/rust/tooling.md · v0.18.0 -->
# Build and test commands

**Toolchain:** Rust is pinned via `rust-toolchain.toml` (channel = `stable`). Every contributor automatically gets the latest stable toolchain on first `cargo` invocation. Required components: `rustfmt`, `clippy`.

Commands live in the `justfile`, which is the single source of truth — do not
copy the underlying cargo invocations into docs or CI, call the recipe.

```bash
just            # list every recipe
just ci         # all four merge gates, in order — run this before every commit
just build      # build all crates
just check      # type-check (faster than build)
just watch      # dev loop, re-checks on save
just fmt        # format in place
just fmt-check  # gate 1
just lint       # gate 2 — clippy, warnings as errors
just test       # gate 3 — nextest (falls back to cargo test) plus doc-tests
just deny       # gate 4 — licenses + advisories
just audit      # CVE check
just release    # optimized build
```

Install `just` and the auxiliary tools once per machine:

```bash
cargo install --locked just
just setup      # cargo-nextest, cargo-watch, cargo-deny, cargo-audit
```

Without `just`, `.cargo/config.toml` defines `cargo lint`, `cargo fmt-check` and
`cargo check-all`. There is no `cargo ci` — a cargo alias can only wrap one
subcommand, so the four gates have to be run in sequence.

## Architecture & Workspace Rules

**Layout:** Cargo workspace, edition `2024`. New code goes in a crate under `crates/<name>/`. The workspace root `Cargo.toml` declares `members = ["crates/*"]` and centralizes shared metadata under `[workspace.package]` and shared dependencies under `[workspace.dependencies]`.

**Crate inheritance:** Crate manifests inherit shared keys from the workspace using `<key>.workspace = true` (e.g. `edition.workspace = true`, `license.workspace = true`). Shared dependencies are referenced as `<crate> = { workspace = true }`.

**MSRV:** Declared in `[workspace.package].rust-version`, `clippy.toml`, and the `msrv` input in `.github/workflows/ci.yml`. Raising it means editing all of them together; the MSRV job compares the last against the first and fails a partial bump. Do not bump it incidentally.

<!-- core/behavior.md · v0.18.0 -->
# Behavioral guidelines

**Maintain the Build:** Never leave the codebase in a state where build, lint,
or tests fail. Run the relevant commands in *Build and test commands* to verify
your work before concluding a task.

**Tradeoff:** Bias toward caution over speed. For trivial tasks, use judgment.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

- State your assumptions explicitly. If uncertain, stop and ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, propose it. Push back when warranted.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked. No abstractions for single-use code.
- No "flexibility" or error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

- Don't "improve" adjacent code, comments, or formatting.
- Match existing style exactly.
- Remove imports/variables/functions that YOUR changes made unused. Don't remove pre-existing dead code unless asked.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

- Transform tasks into verifiable goals (e.g., "Add validation" → "Write tests for invalid inputs, then make them pass").
- For multi-step tasks, state a brief plan and verify each step independently.

<!-- agentcfg:index · v0.18.0 -->
# Extended rules

Read these when they apply; they are not loaded by default.

**By activity:**

- **Any change that ends in a PR:** [Git flow](.agents/git-flow.md) and [Releases and CLI conventions](.agents/cli-conventions.md)
- **Creating branches:** [Branch naming](.agents/branch-naming.md)
- **Reviewing PRs:** [Code review](.agents/code-review.md) and [Rust code review](.agents/rust-code-review.md)
- **Committing code:** [Commit message guidelines](.agents/commit-conventions.md)
- **Deciding what to build next / branching strategy:** [Execution order](.agents/execution-order.md)
- **Opening PRs:** [PR instructions](.agents/pr-guidelines.md)
- **Creating new files:** [Directories and file naming](.agents/rust-file-naming.md)
- **Checking your work:** [Merge gates](.agents/gates.md)
- **Adding or modifying a crate:** [Adding a crate](.agents/new-crate.md)
- **Testing/Verifying:** [Testing instructions](.agents/rust-testing.md)
- **Extending the fragment tree:** [Adding an axis value](.agents/new-value.md)
<!-- agentcfg:end -->
