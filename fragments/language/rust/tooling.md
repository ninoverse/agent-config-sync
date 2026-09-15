---
title: Build and test commands
scope: always
order: -1
---

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
