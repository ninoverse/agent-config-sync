# Claude Code Rust Template

[![CI](https://github.com/ninoverse/claude-mit-rust-template/actions/workflows/ci.yml/badge.svg)](https://github.com/ninoverse/claude-mit-rust-template/actions/workflows/ci.yml)
[![Audit](https://github.com/ninoverse/claude-mit-rust-template/actions/workflows/audit.yml/badge.svg)](https://github.com/ninoverse/claude-mit-rust-template/actions/workflows/audit.yml)

Claude Code configuration scaffolding for **Rust cargo-workspace** projects.
Fork or copy this repo to start a new Rust project that ships with the latest
stable toolchain, opinionated lint/format/test commands, and Claude Code rule
files already wired up.

## What's bundled

| File | Purpose |
|------|---------|
| `Cargo.toml` | Workspace root. `members = ["crates/*"]`, shared `[workspace.package]`, `[workspace.dependencies]` and `[workspace.lints]`. |
| `justfile` | Task runner. Canonical form of every command; CI and the rules call these recipes. |
| `.cargo/config.toml` | Cargo aliases mirroring the justfile, plus a commented faster-linker block. |
| `.github/workflows/ci.yml` | Calls the org's reusable `rust-ci.yml`: four gates, an MSRV job and a coverage artifact. Sets the triggers and the MSRV. |
| `.github/workflows/audit.yml` | Calls the org's reusable `rust-audit.yml`: `cargo audit` + `cargo deny check advisories` on a cron. |
| `.github/workflows/bump-version.yml` | Calls the org's `rust-bump-version.yml`: reads the merged commit's type, bumps the workspace version, pushes a tag. Nothing deploys on it. |
| `renovate.json` | One line extending the org's shared preset. Renovate runs centrally; there is no workflow or token here. |
| `Dockerfile` | Multi-stage build via `cargo-chef`. Stages: `chef`, `planner`, `builder`, `dev`, `runtime`. |
| `compose.yaml` | Local dev container + named volumes for `target/` and the cargo registry. |
| `.dockerignore` | Keeps `target/` and `.git/` out of the build context. |
| `.devcontainer/` | VS Code / Codespaces config reusing the `dev` stage. |
| `rust-toolchain.toml` | Pins channel = `stable` so every contributor auto-pulls the latest stable Rust. |
| `rustfmt.toml` | Format config (edition 2024, 100-col, module-granular imports). |
| `clippy.toml` | MSRV pin for clippy lints. |
| `deny.toml` | `cargo-deny` config: allowed licenses, advisory denials, source restrictions. |
| `.gitignore` | Ignores `target/`, coverage artefacts and secrets. **Not** `Cargo.lock` — see below. |
| `.editorconfig` | Indentation and newline rules for editors without rust-analyzer. |
| `CONTRIBUTING.md` | Setup, the git flow, the gates — the short version of the `.claude/` rules. |
| `.github/CODEOWNERS` | Review ownership, weighted toward the rule files and CI. |
| `.github/pull_request_template.md` | The same What/Why/How/Testing template `.claude/pr-guidelines.md` specifies. |
| `crates/` | Workspace member dir — add crates here via `cargo new --lib crates/<name>`. |
| `crates/example/` | Placeholder crate (lib + bin). A workspace with zero members is a hard cargo error, so this keeps the gates green on a fresh clone and gives the Dockerfile something to build. Delete it *after* adding your first real crate. |
| `CLAUDE.md` | Top-level rules surfaced to Claude Code. |
| `.claude/*.md` | Per-task rule files (see table below). |
| `.claude/settings.json` | Permission allowlist + hooks: rustfmt on save, `cargo check` when Claude stops. |
| `.claude/commands/` | Project slash commands: `/gates`, `/new-crate`. |

### Not in this repository

`SECURITY.md`, `CODE_OF_CONDUCT.md` and `.github/ISSUE_TEMPLATE/` come from
[`ninoverse/.github`](https://github.com/ninoverse/.github), which GitHub serves
as the default to every repository in the organization that has none of its own.
They are not here because both hardcode `ninoverse` URLs, so a copy would be
wrong for anyone else anyway.

`CONTRIBUTING.md` and the pull request template stay, because overriding is
all-or-nothing per file and both are dense with Rust and `just` specifics the
generic versions deliberately drop.

## Bootstrap a project from this template

```bash
# 1. Clone and rename
git clone https://github.com/ninoverse/claude-mit-rust-template my-project
cd my-project
rm -rf .git && git init

# 2. Update workspace identity in Cargo.toml
#    - [workspace.package].repository
#    - [workspace.package].license (if not MIT)

# 3. Install the task runner and auxiliary tools (once per machine)
cargo install --locked just
just setup

# 4. Add your first crate, then drop the placeholder
just new-crate <your-crate>
rm -rf crates/example

# 5. Verify the toolchain and workspace
just ci
```

### If you forked this

`.github/workflows/` calls reusable workflows from
[`ninoverse/.github`](https://github.com/ninoverse/.github). That repository is
public and the calls are pinned to `@v1`, so they keep working in your fork with
no setup — but the job definitions are then maintained by someone else.

To own them outright, copy
[`rust-ci.yml`](https://github.com/ninoverse/.github/blob/main/.github/workflows/rust-ci.yml)
and
[`rust-audit.yml`](https://github.com/ninoverse/.github/blob/main/.github/workflows/rust-audit.yml)
into your own `.github/workflows/` and drop the `uses:` line. They call the same
`just` recipes either way.

Community health files (`SECURITY.md`, issue forms) also come from that
repository. GitHub serves organization defaults only within the owning
organization, so **your fork inherits nothing** — add your own, or GitHub will
show none.

## Daily commands

The `justfile` is the single source of truth for every command — CI and the
`.claude/` rules call these recipes rather than repeating cargo invocations.

```bash
just            # list every recipe
just ci         # all four merge gates — run before every commit
just build      # build all crates
just check      # type-check, faster than build
just watch      # re-check on save
just fmt        # format in place
just test       # nextest (or cargo test) plus doc-tests
just doc        # build and open workspace docs
just audit      # CVE check
```

No `just`? `.cargo/config.toml` defines `cargo lint`, `cargo fmt-check` and
`cargo check-all`. There is no `cargo ci` equivalent — a cargo alias can only
wrap a single subcommand, so run the four gates in sequence.

## Containers

```bash
docker compose up -d dev                     # start the dev container
docker compose exec dev just ci              # run the gates inside it
docker compose run --rm dev cargo build      # or one-shot commands

just docker-build <your-bin>                 # build the runtime image
docker compose --profile app run --rm app    # run it
```

`just docker-build` is the preferred entry point because it stamps the current
commit onto the image as an `org.opencontainers.image.revision` label. Without
`just`:

```bash
docker build --build-arg BIN=<your-bin> --build-arg GIT_SHA="$(git rev-parse HEAD)" .
```

<details>
<summary><b>"failed to read current commit information" warning</b></summary>

Harmless, and not caused by anything in this repo. BuildKit tries to record the
source commit in the build's provenance attestation by shelling out to `git` on
the client. If that call fails, it warns and carries on — the image is fine.

The usual reason is running Docker through `sudo`: git refuses to operate on a
repository owned by another user ("dubious ownership"), so the check fails as
root even though it works as you. It also happens in CI checkouts with no
`.git`.

The OCI label above is unaffected, since the SHA is passed in explicitly — so
you keep commit traceability either way. To remove the warning itself, stop
needing `sudo`:

```bash
sudo usermod -aG docker "$USER"   # then log out and back in
```

Note that docker group membership is equivalent to root on the host; [rootless
mode](https://docs.docker.com/engine/security/rootless/) is the stricter
alternative. To keep using `sudo` instead, tell root's git to trust the
checkout:

```bash
sudo git config --system --add safe.directory "$PWD"
```

</details>

The build uses [`cargo-chef`](https://github.com/LukeMathWalker/cargo-chef) so
the dependency tree compiles into its own cached layer. Without it, editing one
`.rs` file recompiles every dependency on the next build.

Two things worth knowing before you change them:

- **`target/` and the cargo registry live in named volumes**, not on the bind
  mount. Putting them on the mount destroys build times — severely on macOS and
  Windows.
- **`BIN` defaults to `example`**, the placeholder binary. Point it at your own
  crate and delete `crates/example`.

`.devcontainer/` reuses the same `dev` stage, so opening the repo in VS Code or
Codespaces gives you the pinned toolchain with `just`, nextest, deny and audit
already built — no `just setup` wait.

## `Cargo.lock` is committed

Deliberately, and it is the right default for this template. The old advice to
ignore it for libraries was dropped by the Cargo team: committing it makes CI
reproducible, makes `--locked` meaningful, and lets `cargo audit` tell you what
you are actually building. Consumers of a published library ignore your lockfile
anyway, so there is no downside to keeping it.

The MSRV job and every `--locked` build in CI depend on it being present and
current. If a dependency change leaves it stale, CI fails rather than silently
resolving something different.

## Rule files

| File | Purpose |
|------|---------|
| `.claude/git-flow.md` | The branch → commit → PR loop. One branch in flight, no stacked PRs |
| `.claude/branch-naming.md` | Branch prefix and format conventions |
| `.claude/commit-conventions.md` | Conventional Commits rules |
| `.claude/pr-guidelines.md` | PR title, description template, size guidance |
| `.claude/testing-requirements.md` | Test gates (fmt, clippy, nextest, deny) |
| `.claude/file-naming.md` | Workspace and per-crate layout |
| `.claude/code-review.md` | Review checklist (lint, error handling, unsafe, docs, deps) |
| `.claude/crate-workflow.md` | Step-by-step procedure to add a crate |
| `.claude/execution-order.md` | What order to build things in, and one PR per what |
