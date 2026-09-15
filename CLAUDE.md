# CLAUDE.md

This file provides strict guidance and architectural rules for Claude Code (claude.ai/code) when working in this repository.

## Commands & Tooling

- **Toolchain:** Rust is pinned via `rust-toolchain.toml` (channel = `stable`). Every contributor automatically gets the latest stable toolchain on first `cargo` invocation. Required components: `rustfmt`, `clippy`.
- **Maintain the Build:** Never leave the codebase in a state where build, lint, or tests fail. Run the relevant commands below to verify your work before concluding a task.

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

**Automation:** `.claude/settings.json` allowlists these commands so they do not
prompt, runs `rustfmt` on every `.rs` file you edit, and warns if the workspace
stops compiling when a turn ends. Formatting is therefore already handled — do
not run `cargo fmt` after each edit.

## Architecture & Workspace Rules

**Layout:** Cargo workspace, edition `2024`. New code goes in a crate under `crates/<name>/`. The workspace root `Cargo.toml` declares `members = ["crates/*"]` and centralizes shared metadata under `[workspace.package]` and shared dependencies under `[workspace.dependencies]`.

**Crate inheritance:** Crate manifests inherit shared keys from the workspace using `<key>.workspace = true` (e.g. `edition.workspace = true`, `license.workspace = true`). Shared dependencies are referenced as `<crate> = { workspace = true }`.

**MSRV:** Pinned in `clippy.toml` and `[workspace.package].rust-version`. Do not bump it incidentally.

## Behavioral Guidelines

**Tradeoff:** Bias toward caution over speed. For trivial tasks, use judgment.

### 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

- State your assumptions explicitly. If uncertain, stop and ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, propose it. Push back when warranted.

### 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked. No abstractions for single-use code.
- No "flexibility" or error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

### 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

- Don't "improve" adjacent code, comments, or formatting.
- Match existing style exactly.
- Remove imports/variables/functions that YOUR changes made unused. Don't remove pre-existing dead code unless asked.

### 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

- Transform tasks into verifiable goals (e.g., "Add validation" → "Write tests for invalid inputs, then make them pass").
- For multi-step tasks, state a brief plan and verify each step independently.

---

## Extended Rules (Read Before Acting)

Use your file-reading capabilities to read the exact rules in the `.claude/` directory **before** executing any of the following tasks:

- **Any change that ends in a PR:** Read `.claude/git-flow.md` **first** — it defines the branch → commit → PR loop everything else fits inside
- **Adding a crate:** `/new-crate <name>` runs the `.claude/crate-workflow.md` checklist
- **Checking your work:** `/gates` reports which of the four merge gates pass
- **Committing code:** Read `.claude/commit-conventions.md`
- **Creating branches:** Read `.claude/branch-naming.md`
- **Reviewing PRs:** Read `.claude/code-review.md`
- **Testing/Verifying:** Read `.claude/testing-requirements.md`
- **Opening PRs:** Read `.claude/pr-guidelines.md`
- **Creating new files:** Read `.claude/file-naming.md`
- **Building a crate or module:** Read `.claude/crate-workflow.md`
- **Deciding what to build next / branching strategy:** Read `.claude/execution-order.md`
