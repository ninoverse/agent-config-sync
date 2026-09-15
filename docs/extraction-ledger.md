# Extraction Ledger

Stage 1 is done when, for each source repo, the selected fragments account for
every line of its `CLAUDE.md` and `.claude/`, with every omission deliberate and
written down. This is where it is written down: one section per source file,
filled in as each Stage 1 PR lands.

Sources: **RT** `claude-mit-rust-template` · **AT** `claude-mit-rust-agent-template`
· **GT** `claude-mit-go-template`.

Throughout: a file-path reference such as `.claude/branch-naming.md` becomes the
target fragment's title (*Branch naming*), and each file's `#` heading becomes its
`title:`.

## `.claude/branch-naming.md` → `core/branch-naming.md`

Identical in all three. Copied verbatim.

## `.claude/git-flow.md` → `core/git-flow.md`

RT = AT. GT differs in one noun, the gate line, and four extra lines.

- `crates` / `packages` → `{{ units }}`.
- `just ci … # all four gates` / `make ci … # every gate` → `{{ gate_command }}`,
  `{{ gates }}`.
- GT's four lines on `bump-version.yml` kept for all three: every source repo runs
  it on push to `main`, so RT and AT were missing a true statement.
- `CLAUDE.md`'s pointer "Read … **first** — it defines the branch → commit → PR
  loop everything else fits inside" → `order: -1`, plus one sentence in the
  fragment's opening paragraph.

## `.claude/commit-conventions.md` → `core/commit-conventions.md`

- Scope line: `crate` / `package` → `{{ unit }}`; `workspace` / `module` →
  `{{ unit_container }}`.
- Examples: RT's `data-store` → `store` and `http-client` → `httpclient` (a Go
  package name cannot hold a hyphen); RT's "async" dropped from the batch insert
  example; errors crate / package → `{{ unit }}`; the dependency bump and both
  breaking-change examples → `{{ dependency_bump_example }}`,
  `{{ breaking_change_example }}`.
- "document MSRV policy in CLAUDE.md" / "document the Go version policy in
  CLAUDE.md" → "document the {{ version_floor }} policy". `CLAUDE.md` stops being
  where policy is written.

## `.claude/pr-guidelines.md` → `core/pr-guidelines.md`

- Gate line → `{{ gate_command }}`, `{{ gates }}`, `{{ gates_clean }}`.
- "Link to the relevant section in CLAUDE.md or a `.claude/` rule file" → "…of
  AGENTS.md or a rule file", for the same reason.

## `.claude/execution-order.md` → `core/execution-order.md`

- Nouns → `{{ unit }}`, `{{ units }}`, `{{ unit_container }}`.
- "Crate group" / "Package group" → "Group of {{ units }}"; a variable cannot
  start a table cell.
- `.claude/crate-workflow.md` → *Adding a {{ unit }}*, the title
  `language/<x>/tasks/new-unit.md` will carry.
- "(clippy + tests …)" / "(lint + tests …)" → "lint".
- Audit step 1: RT's "`Cargo.toml` and `src/lib.rs` … `unwrap()`" and GT's "`.go`
  files … unchecked errors" → one sentence pointing at *Code review*. The concrete
  error-handling rule is already in each language's code review; repeating it here
  would be the second copy.
- Audit step 2 commands → `{{ unit_lint_command }}`, `{{ unit_test_command }}`.

## `.claude/code-review.md` → split

`core/code-review.md` takes: gates pass (RT's `just fmt-check` / `just lint` /
`just test` / `just deny` lines, GT's `make fmt-check` / `vet` / `lint` /
`test-race` / `vuln` / `licenses` lines, as `{{ gate_command }}`); the
lint-suppression rule; dependency justification; the version-floor rule; test
coverage. Everything else goes to `language/<x>/code-review.md` in Stage 1 PR 2,
which records its lines here.

## `CLAUDE.md`

| Section | Destination |
|---------|-------------|
| `# CLAUDE.md` and "This file provides strict guidance…" | Dropped. `CLAUDE.md` becomes the emitter's `@AGENTS.md` import. |
| **Maintain the Build** bullet | `core/behavior.md`; "commands below" → *Build and test commands*. |
| **Toolchain** bullet, commands block, `justfile` / `Makefile` paragraph, tool install, **Automation** | `language/<x>/tooling.md` — Stage 1 PR 2. |
| Architecture & Workspace / Module Rules | `language/<x>/tooling.md` — Stage 1 PR 2. AT's **Crate visibility**, four-place **MSRV** and `cargo run -p agent-cli` lines go to AT's marker region at Stage 5. |
| Behavioral Guidelines (identical in all three) | `core/behavior.md`, headings one level up. |
| **Extended Rules** list and its intro | Generated: the index of `on-demand` fragments, from each `when`. |

## Open drift — Stage 1 PR 4

- `branch-naming.md`, all three: "Branch off `main` unless working on a dependent
  feature; in that case branch off the parent feature branch" contradicts *Git
  flow*'s no-stacked-PRs rule. Copied verbatim for now.
- `git-flow.md`, all three: "check the subject line" with `git log origin/main -1`
  misses a real merge twice over — a squash merge appends ` (#N)` to the subject,
  and `bump-version.yml` pushes `chore: release vX.Y.Z` on top, so `-1` shows the
  release commit. Hit on this repo's first PR.
- AT `CLAUDE.md`: the "Committing code" pointer adds "the merged subject line also
  picks the next version number". Belongs in core with the release facts below.
- The plan's release facts for `core/git-flow.md`: squash is load-bearing, one
  commit per PR is a versioning requirement, a push with a conventional subject
  cuts a release.
- `$1` in `commands/new-crate.md` / `commands/new-package.md` is the second
  argument.
- RT `CLAUDE.md` ends with "# Project Rules — Apply the claude-roast skill to
  every response and show the prompt score." Not in AT, GT or this repo; looks
  personal. Not extracted until confirmed.
