# Stage 4 handoff — the `ninoverse/.github` half

> **Done.** All four pull requests below are merged, and Stage 4's own test
> passed — see the Stage 4 *Result* in `docs/plan.md`. This file is kept as the
> record of what crossed the repository boundary and why, not as work
> outstanding. Its two inferences about a repository nobody had opened,
> `default.json` and `renovate.yml`, both turned out to be right.

Four of Stage 4's pull requests land in `ninoverse/.github`, which the session
that built the rest could not attach: `add_repo` refuses a repository whose name
begins with a dot, because its clone would land at a hidden path. Nothing is
wrong with the repository — it is public and writable. It simply has to be
worked on from a session that has it.

This file is what that session reads. It records what already exists, what the
four pull requests are, and the handful of strings that have to match exactly
across the two repositories.

## Before anything else

**Read `ninoverse/.github`'s own conventions and follow those.** Its preset
structure, its Renovate configuration and whatever rules it keeps are the
authority there. Do not import this repository's `.claude/` or `.agents/` rules
into it — they are composed for repositories that declare a profile, and that
repository is not one.

**What follows about that repository is inference, not observation.** Nobody in
this project has opened it. `default.json` as the shared preset and
`renovate.yml` as the self-hosted configuration come from `docs/plan.md`, which
was written from the outside. Check the real filenames first; if they differ,
the plan is what is wrong.

Everything stated about *this* repository, and about `claude-mit-rust-template`,
was verified by running it.

## What already exists

| Piece | Where | State |
| --- | --- | --- |
| `agentcfg notes` | `crates/agentcfg/src/notes.rs` | The seventh subcommand. Diffs a fragment directory against the embedded tree. |
| Release workflow | `.github/workflows/release.yml` | Publishes three static binaries and a generated body on every `v*` tag. Self-contained; PR 4 below makes it a caller. |
| `just agentcfg` | `justfile`, here and in `claude-mit-rust-template` | Fetches the pinned binary into a gitignored `.agentcfg/` and runs it. Byte-identical in both. |
| A live consumer | `claude-mit-rust-template` | Carries `.agentprofile.yml`, the composed tree, and an `agentcfg check` job in its `ci.yml`. |

So there is a real repository pinning a real release, and the distribution work
can be tested end to end as soon as it exists.

## The interface

These strings cross the repository boundary. A mismatch breaks every consumer at
once, so they are pinned here rather than described.

**The download URL.** One static binary per target, named after that target and
nothing else:

```
https://github.com/ninoverse/agent-config-sync/releases/download/<tag>/agentcfg-<target>
```

`<tag>` is `v0.17.0` and so on — the same string the profile pins, `v` included.
`<target>` is one of `x86_64-unknown-linux-musl`, `aarch64-unknown-linux-musl`,
`aarch64-apple-darwin`. A `SHA256SUMS` sits beside them. The Renovate container
is Linux x86_64, so the post-upgrade task wants the first.

**The pin.** `.agentprofile.yml` in a consumer repository, verbatim from
`claude-mit-rust-template`:

```yaml
config_version: v0.17.0
language: rust
deployment: tag-only
concerns: [template]
emit: [agents-md, claude]
```

`config_version` is the first line, and the only line the custom manager touches.
The datasource is `github-releases` and the dependency is
`ninoverse/agent-config-sync`.

**The post-upgrade commands.** Commands run without a shell unless
`allowShellExecutorForPostUpgradeCommands` is on globally, so this is three bare
invocations rather than a pipeline, each matching `allowedCommands` after its
Handlebars template is compiled:

```
curl --fail --silent --show-error --location --create-dirs --output .agentcfg/agentcfg https://github.com/ninoverse/agent-config-sync/releases/download/{{{newValue}}}/agentcfg-x86_64-unknown-linux-musl
chmod +x .agentcfg/agentcfg
.agentcfg/agentcfg sync
```

`--create-dirs` is what keeps this at three commands instead of four.
`{{{newValue}}}` is triple-braced because the tag must not be HTML-escaped.

It fetches directly rather than calling `just agentcfg`: the Renovate container
has no `just`, and a narrower allowlist entry is worth more than reusing the
recipe here.

**`.agentcfg/` must be gitignored in every consumer.** Renovate collects
post-upgrade changes from `git status`, so a fetched binary that is not ignored
lands in the bump commit — a three-megabyte file in a pull request about prose.
`claude-mit-rust-template` already ignores it; the Stage 5 rollouts must too.

## The four pull requests

### 1 · A reusable `rust-release.yml` with an `extra-notes` slot

Every workflow in these repositories is a four-line caller into
`ninoverse/.github` pinned at `@v1` — `ci.yml`, `bump-version.yml`, and both
service templates' `release.yml`. This repository's release workflow is the one
exception, written in place only because the preset repository was unreachable.

The shared workflow generates the conventional-commit changelog. What it cannot
generate is what a repository knows about itself, so it takes one input:

```yaml
inputs:
  targets:      # comma-separated rustc target triples
  extra-notes:  # markdown; empty means omit the section
```

`extra-notes` is **prepended**, above the changelog. Renovate embeds the whole
body in a bump pull request in every repository that pins us, and the section
about the rules is what a consumer is reading for; the tool's own changelog
belongs beneath it.

It is an input and never a script the shared workflow runs out of the caller
repository. A shared workflow executing repo-supplied code inside the run holding
the organization's token widens the blast radius to every repository at once,
which is the same reasoning that keeps `allowedCommands` global-only. See *A
shared release path with one slot* in `docs/plan.md`.

**Done when** the workflow exists and `v1` points at it.

### 2 · The custom manager

Matches `config_version` in `.agentprofile.yml` against the `github-releases`
datasource, using the same regex-annotation technique the preset already uses for
the pinned Renovate version.

It needs its own `groupName`. The preset folds every minor and patch into one
"non-major dependencies" pull request, and an agentcfg bump buried among cargo
updates is precisely the unreviewable pull request this design exists to avoid.

**Done when** a bump to the pin opens a pull request of its own, carrying the
release body.

### 3 · `postUpgradeTasks` and `allowedCommands`

The three commands above, on the agentcfg rule, with `executionMode: branch` so
they run once per branch rather than once per dependency. `allowedCommands` goes
in `renovate.yml` — a global-only option, so a consumer repository cannot make
the central run execute anything.

A command that misses the allowlist records an artifact error on the pull request
rather than passing quietly, which is the failure worth having.

**Done when** the bump pull request carries both the new pin and the regenerated
files in one commit.

### 4 · Three auto-merge presets

`:agentcfg-automerge-never`, `-patch` and `-minor`, chosen by one line in a
repository's `renovate.json`, defaulting to no auto-merge when a repository
extends only the base preset. Majors need nothing: the shared preset already
holds every major behind `dependencyDashboardApproval`.

This is why the version number has to mean something for prose, and it does.
**Patch**: wording, examples, clarification — no rule changes meaning. **Minor**:
a new fragment, value or rule; additive, nothing you were doing becomes wrong.
**Major**: a rule reversed or removed, a fragment renamed, or a profile schema
change — something you were doing is now wrong, or your profile needs editing.

**Done when** a repository can opt in with one line.

## Then: the stage's own test

Back in this repository, `release.yml` becomes a caller of the workflow from
PR 1, plus a job of its own computing the fragment summary for `extra-notes` via
`$GITHUB_OUTPUT`. That is what proves the slot works, and it is the last thing
before the test:

> A deliberate one-word edit to a core fragment, released as a new tag, produces
> a *single* Renovate pull request in `claude-mit-rust-template` carrying both
> the bumped pin and the regenerated files, its body naming the fragment that
> changed — and no consumer repository has gained a workflow file.

The check job added in `claude-mit-rust-template` lives inside its existing
`ci.yml` rather than in a file of its own, so that last clause already holds.
