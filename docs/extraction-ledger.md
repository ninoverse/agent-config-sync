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
- `.claude/crate-workflow.md` → *Adding a {{ unit }}*, the title of
  `language/<x>/tasks/new-unit.md`.
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
lint-suppression rule; dependency justification; the "not raised unless
intended" half of the version-floor rule; test coverage.

`language/rust/code-review.md` takes the rest of RT = AT:

- Verbatim: the `[lints] workspace = true` bullet, Error handling, Unsafe code,
  Public API, and the `just deny` bullet. "Breaking changes to a published crate
  bump the major version" stays for now; Stage 1 PR 3 decides whether it belongs
  to `deployment/library/api-stability.md` instead.
- MSRV bullet: its "not bumped" half is in core; "in `clippy.toml` and
  `rust-version`" → a pointer to where *Build and test commands* says it is
  declared.
- "unit or integration test" and "`just test` — unit, integration and doc-tests"
  → one bullet.

`language/go/code-review.md` takes the rest of GT:

- Verbatim: Error handling, Avoid unsafe escapes, Public API, the `make vuln` and
  `make licenses` bullets.
- Lint and format dropped: that `make fmt-check`, `vet` and `lint` pass is core's
  gate check, and what each one runs is in *Testing instructions*.
- `go` directive bullet: "not raised" half in core; the four files that move
  together kept.
- "(table-driven where it fits)" and "`make test-race` passes" → one bullet.

## `.claude/testing-requirements.md` → `language/<x>/testing.md`

GT: verbatim.

RT and AT differ; `language/rust/testing.md` is RT with:

- The "What CI adds" paragraph in AT's wording. Both repos' `ci.yml` call the
  reusable `rust-ci.yml`; RT's text still described the recipes running in
  `ci.yml` itself.
- "A job pinned to 1.85" / "1.86" → "pinned to the MSRV". The number is each
  repo's own and lives in the four places.
- AT's "declared in four places … this job is what catches a partial bump" kept
  without the `Dockerfile`. RT's `Dockerfile` builds with its own
  `RUST_VERSION=1.98`, not the MSRV, so only `Cargo.toml`, `clippy.toml` and
  `ci.yml`'s `msrv` input hold it in both repos. AT pinning its `Dockerfile` to
  the MSRV → AT's marker region, Stage 5.
- AT's rationale for 1.86 (`clap`, `idna_adapter`, the `icu_*` chain through
  `jsonschema`) → AT's marker region, Stage 5.

## `.claude/file-naming.md` → `language/<x>/file-naming.md`

RT = AT, verbatim. GT verbatim except the module path example
`github.com/ninoverse/claude-mit-go-template` → `github.com/ninoverse/<repo>`.

## `.claude/crate-workflow.md` + `commands/new-crate.md` → `language/rust/tasks/new-unit.md`

One skill: the workflow is the body, the command supplies the frontmatter plus
`name: new-crate`, `title: Adding a crate` and `when`.

- The command's "Read `.claude/crate-workflow.md` in full", its copy of the
  pre-flight rules, and "Finish at step 9 …" dropped: each duplicated the workflow
  now in the same file.
- `$1` → `arguments: [name]` and `$name`. A named argument does not depend on how
  indexes count, so this does not wait on confirming the `$1` finding.
- Step 5 test module: AT's three-lint allow and its explanation. RT's workspace
  sets `panic_in_result_fn` too, so RT's two-lint version fails on an `assert!` in
  a test returning `Result`.
- The command's "Points that are easy to get wrong" → *Before committing*, from
  AT's list. AT's `publish` in the inheritance line and "`ToolRegistry` and
  `Agent` in `agent-core`" → AT's marker region, Stage 5.
- Step 5 comment "see .claude/code-review.md" → "see Rust code review".

## `.claude/package-workflow.md` + `commands/new-package.md` → `language/go/tasks/new-unit.md`

Same merge as rust, with `name: new-package`, `title: Adding a package`.

- `$1` → `$name` in prose, `<pkg>` in paths and code.
- The command's "Decide the location before scaffolding" kept, in *Pre-flight*.
- Import path `github.com/ninoverse/claude-mit-go-template/internal/<other>` →
  `<module-path>/internal/<other>`.
- The command's paragraph on the `internal/greet` and `cmd/app` placeholders not
  extracted here: it is about the template, not about Go. Stage 1 PR 3 places it
  in `deployment/template/scope.md` or GT's marker region.

## `commands/gates.md` → `language/<x>/tasks/gates.md`

Verbatim apart from `name`, `title` and `when`, and the path reference.

## `.claude/settings.json` → `language/<x>/settings.partial.json`

RT = AT. Verbatim. RT's `settings.local.json` is not extracted: it is the personal
override, enabling the `claude-roast` plugin.

## `CLAUDE.md`

| Section | Destination |
|---------|-------------|
| `# CLAUDE.md` and "This file provides strict guidance…" | Dropped. `CLAUDE.md` becomes the emitter's `@AGENTS.md` import. |
| **Maintain the Build** bullet | `core/behavior.md`; "commands below" → *Build and test commands*. |
| **Toolchain** bullet, commands block, `justfile` / `Makefile` paragraph, tool install | `language/<x>/tooling.md`, verbatim. |
| RT's `.cargo/config.toml` alias paragraph | `language/rust/tooling.md`. Not in AT, which has no `.cargo/config.toml` — see open drift. |
| **Automation** | `language/<x>/automation.md`, `emit: [claude]`. "allowlists these commands" → "the commands in *Build and test commands*". |
| Architecture & Workspace / Module Rules | `language/<x>/tooling.md`. Rust's **MSRV** line in AT's wording minus the `Dockerfile`, which only AT pins to the MSRV (RT builds with `RUST_VERSION=1.98`); that part → AT's marker region. GT's `claude-mit-go-template` import path → `<module-path>`. |
| AT's **Crate visibility** and `cargo run -p agent-cli` lines | AT's marker region, Stage 5. |
| Behavioral Guidelines (identical in all three) | `core/behavior.md`, headings one level up. |
| **Extended Rules** list and its intro | Generated: the index of `on-demand` fragments and task pointers, from each `when`. |
| RT's "# Project Rules — Apply the claude-roast skill …" | Dropped: personal, from the plugin RT's `settings.local.json` enables. |

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
- `crate-workflow.md` step 2, RT and AT: the manifest template says
  `version = "0.1.0"`, but every crate in both repos inherits
  `version.workspace = true`, and the workspace comment says `bump-version.yml`
  refuses to tag when crate versions diverge. Copied verbatim for now.
- `.cargo/config.toml` aliases: `language/rust/tooling.md`, the rust `gates`
  fallback and the settings allowlist all name `cargo lint`, `cargo fmt-check` and
  `cargo check-all`; AT has no `.cargo/config.toml`. Either AT gains the file or
  the aliases go.
- `commands/gates.md`: GT says `make ci` stops at the first failing target, so
  later gates are "not run"; `just ci` stops the same way, and the rust command
  does not say so.
