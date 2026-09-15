# Contributing

The rules that govern this repository live in [`CLAUDE.md`](CLAUDE.md) and
[`.claude/`](.claude/). They are written for Claude Code but they are not
agent-specific — they are the conventions, and they apply to humans identically.
This file is the short version and points at the authoritative one for each
topic.

## Setup

```bash
cargo install --locked just
just setup      # cargo-nextest, cargo-watch, cargo-deny, cargo-audit
just ci         # confirm a clean checkout passes
```

The toolchain installs itself: [`rust-toolchain.toml`](rust-toolchain.toml) pins
the channel, so the first `cargo` command pulls the right compiler.

Prefer a container? `docker compose up -d dev && docker compose exec dev just ci`,
or open the repo in VS Code and reopen in the devcontainer — the tooling above
is already built into the image.

## The loop

One branch, one commit, one PR, merged before the next begins. No stacked PRs.
Full rules in [`.claude/git-flow.md`](.claude/git-flow.md).

```bash
git switch main && git pull --ff-only
git switch -c <type>/<short-description>     # .claude/branch-naming.md
# ... change ...
just ci                                      # must pass before you push
git commit                                   # .claude/commit-conventions.md
git push -u origin <branch>
```

Then open a PR using the template. If Claude Code prepared the branch, it stops
before opening the PR by design — that step is yours.

## The four gates

```bash
just ci
```

`fmt-check` · `lint` · `test` · `deny`. All four, zero warnings, before you push.
CI runs the same recipes, one job per gate, plus an MSRV job.
See [`.claude/testing-requirements.md`](.claude/testing-requirements.md).

## Adding a crate

Follow the nine steps in
[`.claude/crate-workflow.md`](.claude/crate-workflow.md) — or run `/new-crate
<name>` in Claude Code, which executes them.

Two things that are easy to miss and that the gates will catch:

- `[lints] workspace = true` in the crate manifest. Without it the crate opts out
  of the workspace lints entirely.
- `#![allow(clippy::unwrap_used, clippy::expect_used)]` inside the test module.
  Those lints are workspace-wide and fire in test targets too.

## What gets declined

This template biases toward simplicity. Additions that only serve one downstream
project, abstractions with a single caller, and configuration for situations that
have not happened yet are likely to be turned down — see the Behavioral
Guidelines in [`CLAUDE.md`](CLAUDE.md).

## Releases

Merging to `main` bumps `[workspace.package].version` from the subject of the
merged commit and pushes a matching tag — `feat` minor,
`fix`/`perf`/`refactor`/`chore`/`docs` patch, `!` or `BREAKING CHANGE` major.
Anything else bumps nothing. So the commit convention in
[`.claude/commit-conventions.md`](.claude/commit-conventions.md) is not only
documentation: it picks the version number.

Nothing deploys on that tag. This is a template; the tag exists so someone can
point at the version of it they copied. The workflow is not defined here — it
calls [`ninoverse/.github`](https://github.com/ninoverse/.github) and needs
organization-level app credentials.

Tagging by hand competes with it rather than complementing it. Don't.

## Dependency updates

Renovate opens them. It runs **centrally**, from
[`ninoverse/.github`](https://github.com/ninoverse/.github), so there is no
workflow and no token in this repository. `renovate.json` here is one line
extending the shared preset; deleting it would opt this repository out.

Review the changelog rather than rubber-stamping, and check that the MSRV job
still passes: a dependency raising *its* MSRV is the usual reason that job goes
red. Majors wait for approval on the Dependency Dashboard issue; everything
non-breaking arrives as one grouped PR on Monday. Security fixes ignore the
schedule entirely.

The shared preset is configured **not** to touch `dtolnay/rust-toolchain`. The
MSRV job pins it to the `rust-version` in `Cargo.toml` deliberately — bumping it
would leave the job green while it quietly stopped testing anything. Raising the
MSRV is a deliberate edit to `Cargo.toml` and `clippy.toml` together, and the
job's pin moves with it.

Anything that should change for *every* project — the schedule, the grouping,
the major-approval gate — belongs in the org preset, not here. Overriding it
locally is possible but reintroduces exactly the drift centralizing removed.

## If you forked this

Two things in this repository point at `ninoverse` and will not work as-is:

- `renovate.json` extends `github>ninoverse/.github`. Replace it with your own
  policy, or point it at your own preset.
- `.github/workflows/` calls reusable workflows from that same repository. They
  are public and pinned to `@v1`, so they keep working — see the README for how
  to vendor them instead.

`SECURITY.md` and the issue forms are **not** in this repository; they come from
the organization defaults, which a fork does not inherit. Add your own.
