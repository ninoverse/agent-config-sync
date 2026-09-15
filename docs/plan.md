# agent-config Rollout

Centralising Claude, Codex, Copilot and Cursor instructions for the ninoverse repositories into single-axis fragments, composed per repo by a Rust binary and synced as ordinary committed files. Seven stages, sequenced so nothing is built before the thing it depends on is proven.

**30** fragments in v1 · **~75** repos they compose into · **6** axes, one declared empty · **2** emitters in v1 · **1** new file per consumer repo · **30+** agents reading the output

> **Status:** design settled, implementation not started.
> Every decision below was reached deliberately; the *Decisions locked in* section
> exists so they are not relitigated. Four questions remain genuinely open, each
> tied to the stage that closes it — see *What could go wrong*.
>
> **Start here:** Stage 1. Stage 0 is done — `docs/stage-0-spec-read.md` records
> what the spec says and what it moved. Stage 1 is editorial, not code — no Rust
> is written until Stage 2.
>
> A rendered version of this document lives at
> <https://claude.ai/artifact/2iMBD8bNNRRuC7gzVB7o1d>. This file is the canonical
> copy; update it here and the rendered one follows, never the other way round.

## The axes

Three levels, and keeping them straight is the whole model: an **axis** is a dimension, a **value** is one option on that axis, and a **fragment** is a single markdown file inside a value. A repository picks values; the tool collects the fragments inside them.

```text
fragments/
├── core/                  always included — nothing to pick
│   ├── git-flow.md        ← a fragment
│   └── … 6 fragments
├── language/              ← an axis   pick exactly 1
│   ├── rust/              ← a value   7 fragments inside
│   │   ├── tooling.md     ← a fragment
│   │   └── …
│   └── go/                7 fragments inside
├── architecture/          ← an axis   pick 0 or 1
│   └── ddd/               4 fragments inside
├── deployment/            ← an axis   pick exactly 1
│   ├── service/  library/  template/  cli/
└── concerns/             ← an axis   pick any number
    ├── data-access/  sync/
```

`core/` is not an axis — it has no values and is always included, which is why it has no cardinality. The six real axes each have a cardinality: how many of that axis's values a single repo may name in its profile. Two languages exist, but a repo declares exactly one of them; five concerns will exist, and a repo may declare none, one or all five. That is what the schema enforces:

| Axis | How many values / one repo declares | Values that exist / to choose from | Fragments / per value | Covers |
| --- | --- | --- | --- | --- |
| language | exactly 1 — `language: rust` | rust, go | 7 | Tooling vocabulary, code-review idioms, testing, file naming, permissions, hooks |
| framework | 0 or 1 — `framework: ~` | **none yet** | — | Axum, Dioxus and the rest. The schema accepts the axis; no value is written until a repo needs one. |
| architecture | 0 or 1 — `architecture: ddd` | ddd | 4 | The structural discipline the code commits to: layer dependency direction, aggregate and value-object rules, where repository interfaces live, bounded contexts. Language-neutral. `hexagonal` and `event-sourced` await a repo that needs them — and a repo picks one lane, because two architectures can contradict each other in a way two concerns never can. |
| deployment | exactly 1 — `deployment: service` | service, library, / template, cli | 1 | Release consequences, config and shutdown discipline for a service; semver, API stability and doc coverage for a library; exit codes and stream discipline for a cli. |
| concerns | any number, / including none — `concerns: [sync]` | data-access, sync | 1 | Language-neutral and path-scoped, so they load only when Claude touches matching files. Heavy-calc and fetching deferred. |
| sensitivity | exactly 1, defaulted — `sensitivity: none` | **none only** | 0 | Payload logging, error-message contents, retention, encryption at rest, audit trail. Declared now because retrofitting it across dozens of repos later is the expensive case. |

So v1 authors **30 fragments** — 6 core, 7 each for rust and go, 4 for `ddd`, 4 across the deployment values, 2 concerns. At full spread (five languages, a dozen frameworks, five concerns, a handful of architectures) it lands near 70, still serving ~75 repos.

The whole per-repo footprint is one file. This is what `claude-mit-rust-agent-template`'s would actually say today — note the empty framework and concern picks, which is what "0 or 1" and "any number" look like in practice:

```yaml
# .agentprofile.yml
config_version: v1.0.0
language:    rust          # exactly 1
framework:   ~             # 0 or 1 — none yet
architecture: ddd           # 0 or 1
deployment:  service       # exactly 1
concerns:  []            # any number — none yet
sensitivity: none          # exactly 1, defaulted
emit:        [agents-md, claude]
```

That profile composes **18 fragments**: 6 core + 7 rust + 4 ddd + 1 deployment. Drop the `architecture` line and it is 14. `claude-mit-rust-template` composes 14 too — same core, same rust — differing in exactly one fragment, `template/scope.md` instead of `service/release.md`. That single fragment is the difference between a stray push to `main` costing a junk tag and a stray push deploying to Cloud Run, which is the clearest argument for deployment being an axis at all.

### Why deployment is an axis and concurrency is not

Deployment is already differentiated across the three existing repos, and it is the axis the bump-version finding below actually turns on: `claude-mit-rust-template` is a `template` with no deploy, the other two are `service` repos wired to Cloud Run. The rules genuinely diverge — graceful shutdown and env-driven config on one side, semver and public-API stability on the other — and neither belongs to language or concern.

Architecture qualified on the same test but by a different route: it has no value in any repo yet, but one value — `ddd` — is a large, coherent, language-neutral body of rules that will be declared by several repos rather than one. That is the reuse ratio an axis has to clear, and a business-domain axis (billing, telemetry) fails it badly: roughly forty values for seventy-five repos is relocation, not centralisation. Domain rules stay in the marker region.

Sensitivity is the opposite case: no content today, but declaring `sensitivity: none` costs one line now and retrofitting the axis across dozens of repos later does not. Concurrency model, protocol and visibility were all considered and rejected — the first two are determined by framework or language, and the third is a variable that two paragraphs reference, not a body of rules.

> **Central first** — No repo declares a value that agent-config has not released. Adding F# is `language/fsharp/`, then a release, then the consuming repo's pin — two PRs in two repos, in that order. Nobody has to remember it: valid values are the embedded directory listing, so `language: fsharp` is a hard error until that directory ships. Axes are the expensive thing and stay guarded — one is a field in every profile, a dimension in every emitter test, and a question every new repo must answer. A value is only a directory, paid for by the repos that name it.

## Stages

Sequenced by dependency, and shaped to the no-stacked-PRs rule in `.claude/execution-order.md`: each stage is one branch, one PR, merged before the next is cut.

### Stage 0 · ~30 min — Read the AGENTS.md spec directly

Everything downstream assumes the spec's shape, and this environment's egress proxy blocked `agents.md` — the design rests on secondary sources. Read the primary document and confirm three things — plus one that is not in it.

- No frontmatter convention that collides with `scope:` / `paths:`.
- Whether nested files *replace* or *supplement* the parent — this decides whether concern rules may ever be emitted as nested `AGENTS.md` files rather than root-level pointers.
- Recommended section headings worth matching, so the output reads as idiomatic AGENTS.md rather than a transliterated CLAUDE.md.
- Not the spec, but check it here too: whether a skill is slash-invocable, whether it receives arguments, and whether `allowed-tools` has a skill equivalent. Those three answers set the default for `surface:` (renamed `invocation:` by the result), and getting them wrong is a regression in ergonomics rather than a redesign.

> **Done when** — A note records what the spec actually says, and either confirms the emitter design unchanged or lists exactly what moves. It lands as the first commit of Stage 1 — the repo does not exist yet.

> **Result** — `docs/stage-0-spec-read.md`. AGENTS.md design unchanged; four things moved, all applied below: `surface:` became `invocation:`, the budget counts only model-invocable skill descriptions, HTML comments are uncounted, and the existing `$1` argument references are drift. It landed as its own docs PR rather than inside Stage 1: this repo already existed, and git-flow allows one commit per branch.

### Stage 1 · ~1 day — Extract the fragments — the single-axis refactor

The substance of the whole project, and entirely independent of the tooling. Create `ninoverse/agent-config` scaffolded from `claude-mit-rust-template`, then populate `fragments/` by hand from the three existing repos. No binary yet — hand-verified markdown only.

The pivotal pair is `language/<x>/values.yml` and its `tooling.md`. The first declares the vocabulary — unit noun, gate command, formatter — which core fragments then reference as `{{ unit }}` and `{{ gate_command }}`; the second carries the command table and the prose around it. Together they are what lets `core/` be written once and still read as though it were written for Rust.

Six passes, in order:

1. **core/** — six fragments, vocabulary neutralised.
2. **language/rust/** and **language/go/** — including the new tooling fragment and the permissions/hooks partial.
3. **deployment/service/**, **library/** and **template/** — new content, and the axis all three existing repos already differ on.
4. **architecture/ddd/** — new content, four fragments, and the first axis whose rules reach across every layer of a repo that declares it.
5. **concerns/data-access/** and **concerns/sync/** — new content, two of five, enough to prove the axis carries.
6. **Reconcile drift** found along the way (see the map below).

Draft the fragment-authoring guide as you go — single-axis discipline, vocabulary neutralisation, what makes something core rather than language. Stage 6 edits it into shape, but the judgement being exercised here is the content, and reconstructing it later is archaeology.

> **Done when** — For each of the three repos, the selected fragments concatenated by hand account for every line currently in its `.claude/` — with each omission deliberate and written down.

### Stage 2 · ~2 days — Build the `agentcfg` crate

One crate in the workspace, `lib` plus `bin`. It never parses markdown — bodies pass through untouched but for one `{{ name }}` substitution pass, so the work is frontmatter splitting, selection, substitution and emission.

```bash
# the whole surface
agentcfg sync   [--repo <path>] [--fragments <path>]  # write
agentcfg check  [--repo <path>]                       # drift or overrun → 1
agentcfg plan   [--repo <path>] [--format markdown]   # what changes, and why
agentcfg why    "never use unwrap"                    # which fragment says this
agentcfg init   --language rust --concern data-access # scaffold a profile
agentcfg eject                                        # unmanage, keep the files
```

The first three run the same computation and differ only in sink: selection produces `Vec<OutputFile>`, and `sync` writes it, `check` compares it, `plan` prints it. Drift detection costs nothing extra because it is the same code path. `why` is a lookup over that same selection; `init` and `eject` are the two ends of a repo's lifecycle under the tool.

Almost nobody types any of it. A repo meets `init` once, then experiences this system as a Monday pull request and, on a bad day, a red `check`. That is the interface that has to be good; the CLI is for authoring fragments and for the two moments something goes wrong.

- **Emitters** behind one trait: `agents-md` and `claude`. Cursor waits — Cursor reads AGENTS.md natively. The claude emitter writes every task fragment to `.claude/skills/<name>/SKILL.md` and reads `invocation:` to decide whether it adds `disable-model-invocation: true`. It never writes `.claude/commands/` — commands have been merged into skills.
- **Golden-file tests** under `tests/fixtures/<profile>/`, which fits the existing test gate exactly.
- **Fragments embedded** in the binary at build time, so `config_version` pins content and code together and can never desync. `--fragments` overrides for local iteration.
- **Substitution is ~30 lines, hand-rolled** — scan for `{{ name }}`, resolve against the selected values, and stop. Hand-rolled rather than minijinja precisely so nobody switches conditionals back on later. An unresolved name is a hard error, never an empty string — silently emitting `run` with nothing after it is the worst failure this system could have — and literal braces need an escape, with a real case waiting in the fragment that documents Renovate's own `{{{newValue}}}` templates.
- **Valid values are the directory listing** — the embed step emits the value set alongside the fragments, so `language: fsharp` becomes legal the moment `language/fsharp/` ships in a release, and is a hard error before that. Never a hand-written enum: that would make every new language a code change and quietly undo the axis design.
- **Provenance on every block** — each emitted span opens with `<!-- language/rust/tooling.md · v1.3.0 -->`. That comment is what turns `why` into a lookup rather than a text search, and what makes the Monday diff readable at the hunk level.
- **Budget measured, not remembered** — `check` reports the composed always-on size and fails past a threshold declared centrally (200 lines to start). Path-scoped content is uncounted, since it is the always-on set that costs every session — but the *descriptions* of model-invocable skills are counted, because those load every session too and would otherwise be spend the gate cannot see. An `invocation: user` skill's description never enters context, so it is uncounted. So are HTML comment lines — markers and provenance — which Claude Code strips before loading; counting them would spend 18 of the 200 lines on the reader that does not need them.
- **Empty globs warn** — a `paths:` pattern matching zero files in the repo is reported by `check`. A warning, not a failure: a young repo may legitimately not have that layout yet.
- **A damaged marker region is a hard error** — missing end marker, nested markers, markers out of order. `sync` refuses and leaves the file untouched rather than guessing where generated content ends.
- **`init` detects what it can** — `Cargo.toml` or `go.mod` pre-fills `language`. Everything else is a flag or a default, because everything else is genuinely a choice. It prompts only when stdin is a TTY *and* a required value is still missing; `--non-interactive` turns that into a hard failure. Flags always win, so an agent scaffolding a repo from the template never sees a question.
- **`why` ships as a skill too** — the claude emitter writes a model-invocable `/why` next to `/gates` and `/new-crate`. The agent obeying these rules is the one most likely to need to trace one, and mid-session is exactly when the distance to the central repo hurts.
- **The profile schema is written down** — one documented reference for every field, its cardinality, its default and whether it is required. It has accreted across design rather than being specified in one place, and the tool that validates it is the natural home for the document.
- **`sync` never writes `.agentprofile.yml`** — it only reads it. That is a correctness constraint, not a preference: Renovate's custom manager owns that file during a bump, and a post-upgrade task that rewrites a file the manager already changed has its version silently discarded.
- **The claude emitter owns `.claude/settings.json`** — composed from the language value's `settings.partial.json` plus the profile's `settings_extra:`, written whole, verified byte-for-byte. No key-level merge, because JSON cannot carry a marker region.
- **Error messages are the interface** — the tool never prompts, so its failures carry the whole UX. A drift failure names the file, the fragment owning the changed block, and the one command that fixes it. A budget failure lists the always-on fragments with line counts, largest first, so the thing to move behind `scope: paths` is the first line you read.

> **Done when** — `just ci` is green and the golden fixtures cover: rust, go, a two-concern profile, a profile whose concern was removed (proving the manifest deletes the orphaned rule file), an always-on set over budget (proving `check` fails), and a mangled marker region (proving `sync` refuses).

### Stage 3 · ~half day — Pilot against `claude-mit-rust-template`

The cleanest of the three — no repo-specific extras to confuse the signal. Run `agentcfg sync --fragments ./fragments` against a local checkout and diff the generated tree against the current `.claude/`.

Then iterate the *fragments*, not the emitter, until every remaining difference is one you intended. This is where Stage 1's editorial work is actually validated; expect to spend most of the half day here, not in code.

> **Done when** — The diff contains only intended changes and `agentcfg check` is green, budget included — Stage 2 measures the always-on set, so this stage does not count lines by hand.

### Stage 4 · ~half day — Distribution — the update rides Renovate

Five pieces, and not one of them is a workflow in a consumer repository. The central self-hosted Renovate run in `ninoverse/.github` already updates every opted-in repo on a whole-installation App token; agentcfg becomes one more dependency it knows how to bump, which is what removes the per-repo sync workflow entirely.

- **Release workflow** in agent-config — static binaries for linux-musl x86_64/aarch64 and macOS aarch64, attached to a tagged release, plus **generated release notes** listing the fragments added, changed and removed. Renovate embeds release notes for the `github-releases` datasource, so that summary becomes the body of every bump PR in every repo, written once instead of computed seventy-five times. The repo is public, so every download is unauthenticated `curl`.
- **Custom manager in `default.json`** — matches `config_version` in `.agentprofile.yml` against the `github-releases` datasource, the same regex-annotation technique already used for the pinned Renovate version. It needs its own `groupName`: the preset currently folds every minor and patch into one "non-major dependencies" PR, and an agentcfg bump buried among cargo updates is precisely the unreviewable PR this design exists to avoid.
- **`postUpgradeTasks` on that rule** — runs `agentcfg sync` after the pin is bumped and *before the commit is made*, so the new pin and the regenerated files land in one commit and `main` is never inconsistent. `executionMode: branch`, with `allowedCommands` set in `renovate.yml` — a global-only option, so a consumer repository cannot make the central run execute anything. Commands get no shell by default, so this is three bare invocations in sequence — fetch the pinned binary, mark it executable, run `sync` — each matching the allowlist after its template is compiled.
- **Three auto-merge presets in `.github`** — `:agentcfg-automerge-never`, `-patch`, `-minor`, chosen by a second line in the repo's `renovate.json`. Majors need nothing added: the shared preset already puts every major behind `dependencyDashboardApproval`.
- **`agentcfg check` as a CI gate**, plus the **`just agentcfg` recipe** that fetches the pinned version into a gitignored cache — no global install and no toolchain, since the Go repos have no Rust. Together they cover the other direction: when someone edits their profile to add a concern, `check` fails in their own PR and the fix is one command locally. Better than a bot regenerating it afterwards, because the person making the change sees the result. agent-config runs the same recipe against the *previous* release, which is how it eats its own output without a build loop.

No new schedule either — the central run is already on `before 6am on monday`.

> **Done when** — A deliberate one-word edit to a core fragment, released as a new tag, produces a *single* Renovate PR in the pilot repo carrying both the bumped pin and the regenerated files, its body naming the fragment that changed — and no consumer repository has gained a workflow file.

### Stage 5 · ~half day — Roll out and decommission

`claude-mit-go-template` first — it validates that the core fragments really are language-neutral, since it is the repo that diverged most.

Then `claude-mit-rust-agent-template`, which is the interesting one: it carries the only genuinely local content in the set (the measured MSRV rationale naming `clap` and the `icu_*` chain, the extra `panic_in_result_fn` allow, the reusable-workflow reference). It proves the escape hatch.

Each rollout PR deletes that repo's old `.claude/*.md` in the same commit that adds the generated tree, so no window exists where both are live and disagreeing.

> **Done when** — All three repos carry only `.agentprofile.yml` plus generated files, `agentcfg check` is green in each, and the agent-template's local content survived regeneration untouched.

### Stage 6 · ~half day — Close the loop — agent-config adopts itself

The stage that decides whether this survives a year of nobody touching it. Everything before produces configuration for other repositories; this one makes agent-config an ordinary consumer of its own output and writes down how to extend it.

- **agent-config gets a profile** — `language: rust`, `deployment: cli`. Which means writing `deployment/cli/conventions.md`, the value no repo needed until now: exit codes, stdout versus stderr, `--help` quality, and the non-interactive rule this plan already locked. Its own `AGENTS.md` is composed rather than hand-written, with the authoring guide in its marker region.
- **`/new-value <axis> <name>`** — a numbered checklist in the shape of the existing `/new-crate`: create the directory, write the fragments that axis's other values carry, add a golden fixture, bump minor, release, then bump the consumer's pin. Adding F# becomes a command instead of an archaeology exercise, and the same command serves a new concern or architecture.
- **The fragment-authoring guide** — drafted during Stage 1 while the editorial judgement is actually being made, edited into shape here. Single-axis discipline, vocabulary neutralisation, core versus language, choosing `scope`, the always-on budget, and the profile schema reference from Stage 2.

> **Done when** — `agentcfg check` is green against agent-config itself, and someone who has never seen the repo can add a language value working only from `/new-value` and the guide.

## Fragment extraction map

Where each existing file lands. Derived from diffing the three repos rather than guessed — the notes column records what the diff actually showed.

| Axis | Fragment | Source today | Note |
| --- | --- | --- | --- |
| core | git-flow.md | git-flow.md | 97% universal. Three diffs only: one noun, one command line, and four lines the Go repo has and the Rust repos are missing — see the drift note below. |
| core | branch-naming.md | branch-naming.md | **byte-identical in all three** Copy verbatim; zero editorial work. |
| core | commit-conventions.md | commit-conventions.md | Structure identical. Only the worked examples and the scope noun need neutralising. |
| core | pr-guidelines.md | pr-guidelines.md | One line differs across repos: the gate command. Neutralise and it is universal. |
| core | execution-order.md | execution-order.md | Universal once crate/package becomes the unit noun defined by the language fragment. |
| core | code-review.md | code-review.md **split** | Only the review *process* is universal. The language idioms below are a separate fragment, not a rendering of this one. |
| language | tooling.md + values.yml **order: 0** | new | The command table, plus the `values.yml` declaring unit noun, gate command and formatter for every core fragment to reference. `order: 0` is now presentation — substitution means nothing depends on reading it first. |
| language | code-review.md | code-review.md | The unwrap/expect ban and unsafe policy for Rust; the errcheck and wrapping rules for Go. Genuinely different rules, not different words. |
| language | testing.md | testing-requirements.md | The one file that already differs between the two Rust repos. The agent-template's extra MSRV rationale goes to its local region, not here. |
| language | file-naming.md | file-naming.md | **~95% language-specific** Layout and naming tables throughout. Goes entirely to language — no core half worth extracting. |
| language | tasks/new-unit.md | crate-workflow.md / package-workflow.md | Task-shaped, `invocation: model`. Emitted into AGENTS.md as a pointer and as `.claude/skills/` for Claude — model-invocable because "add a crate" said in prose should run the nine steps, which a user-only skill never sees. Takes a named `arguments:` list rather than `$1` — see the drift note below. |
| language | tasks/gates.md | commands/gates.md | Same treatment as above. |
| language | settings.partial.json | .claude/settings.json | Permission allowlist plus the formatter and build-check hooks. Claude-only, merged by the claude emitter. |
| architecture | ddd/layers.md | new | `scope: always`. The layer model and dependency direction — the domain layer imports nothing. Also carries the build-order supplement: domain unit first, then application, then infrastructure. |
| architecture | ddd/domain-model.md | new | `paths: **/domain/**`. Entities, value objects, aggregates. Immutability and value equality; the aggregate as transaction boundary; reference other aggregates by ID, never by pointer. Naming goes through the glossary: check it before introducing or renaming a type, and add the term in the same commit. This fragment carries the enforcement because it is the one already scoped to the domain layer. |
| architecture | ddd/repositories.md | new | `paths: **/repository/**, **/infrastructure/**`. The interface lives in the domain, the implementation in infrastructure; it returns aggregates, never rows, and no persistence type crosses back. |
| architecture | ddd/boundaries.md | new | `scope: always`. Bounded contexts, ubiquitous language, and an anti-corruption layer at every external boundary. Also fixes the **glossary convention**: every context keeps its ubiquitous language at `docs/domain/glossary.md`, a plain doc a domain expert can read and correct. Types carry their own definition as a doc comment — that copy cannot drift; the glossary covers everything that is not a type, plus the synonyms this context deliberately rejects. Never centralised: a glossary shared across contexts is the universal-`Customer` mistake in new clothes. |
| deployment | service/release.md | new | What a push to `main` actually costs when a tag deploys, plus env-driven config, `PORT`, graceful shutdown, health checks. Carries the bump-version facts below. |
| deployment | library/api-stability.md | new | Semver discipline, public-API stability, deprecation path, doc coverage on exported items. |
| deployment | template/scope.md | new | Keep the example minimal, no real business logic, the tag is a marker rather than a release. This is what all three current repos actually are. |
| deployment | cli/conventions.md | new | Written at Stage 6, because agent-config is itself a CLI and becomes the first repo to declare the value. Exit codes, stdout versus stderr, `--help` quality, and the non-interactive rule. |
| concerns | data-access/rules.md | new | Language-neutral, `scope: paths`. Transactions, N+1, forward-only migrations, lock discipline. |
| concerns | sync/rules.md | new | Idempotency keys, ordering guarantees, at-least-once semantics, conflict resolution. |
| concerns | heavy-calc/ · fetching/ · … | new | **deferred** Write them when a repo needs them. The schema already supports the axis. |

### Drift found while mapping

All three repos run `bump-version.yml` on `push: branches: [main]`. The called workflow reads the *first line only* of `github.event.head_commit.message`, matches conventional-commit prefixes, and pushes a tag with a GitHub App token — chosen specifically so downstream workflows do fire. The trigger is the push, not the merge, and GitHub cannot tell a hand-push from a merge here.

| Repo | Tag triggers deploy | Hazard documented |
| --- | --- | --- |
| claude-mit-rust-template | No — no `release.yml`; the tag is only a marker | **no** |
| claude-mit-rust-agent-template | **Yes → Cloud Run** `agent-server` | **no — the real gap** |
| claude-mit-go-template | **Yes → Cloud Run** `app` | **yes** |

The one repo that documents the hazard is not the one most exposed to it. The Rust variant is also messier when it fires: `cargo set-version` commits `Cargo.toml` and `Cargo.lock` back to `main` as `chore: release vX.Y.Z`, so a stray push leaves a commit you did not write on the branch you just pushed to. The Go one only tags.

Two further findings, both worse, both undocumented in every repo:

- **Merge commits silently disable releases.** The parser matches `^[a-z]+`; a `Merge pull request #12 from …` subject matches nothing, so `bump=skip`. Set any repo to "Create a merge commit" and releases stop happening while the workflow keeps reporting success. Squash, or rebase with conventional subjects, is load-bearing.
- **"One commit per PR" is a versioning requirement, not a style rule.** Only `head_commit` is read. A PR landing `feat: X` then `fix: Y` gets a *patch* bump, shipping the feature under a version that claims none was added. `git-flow.md` already mandates one commit — with the actual reason recorded nowhere.

Three facts for `core/git-flow.md`, none of which exist today: a push to `main` with a conventional subject cuts a release, and where a `release.yml` exists that means a deploy; the merge strategy must be squash; one commit per PR is correctness. This is what centralisation buys first — the gap is only visible when the doc and the workflow are read side by side.

One more, found at Stage 0 and unrelated to releases: **the unit-creation command reads the wrong argument.** `new-crate.md` and `new-package.md` in all three repos say "Add a new crate named `$1`". Skill arguments are 0-based — `$0` is the first — and a missing index stays literal, so `/new-crate foo` asks for a crate named `$1`. Found from the docs rather than by running it: invoke `/new-crate` once in a template repo to confirm before reconciling.

## Decisions locked in

Settled during Phase 2, recorded here so Stage 2 does not relitigate them.

**AGENTS.md canonical** — Primary artifact, not a fallback. `CLAUDE.md` is a two-line `@AGENTS.md` adapter. If an emitter breaks, every agent still reads AGENTS.md and nothing is lost.

**Embedded fragments** — Compiled into the binary, so one downloaded artifact is the whole contract and `config_version` pins content and code atomically. A fragment edit therefore requires a release — which is correct, not a cost.

**No new credential** — Corrects an earlier reading of this. The plan first argued for repo-self-sync because a central push "would need an App with write access to every repo" — but that App already exists: the self-hosted Renovate run in `ninoverse/.github` holds a whole-installation token and is already the org's answer to "a central thing changed, update every repo". agentcfg introduces no credential of its own, it becomes another dependency that mechanism already knows how to bump. The blast radius does not widen either, because `allowedCommands` is global-only: a consumer repo cannot make the central run execute anything. The only token a consumer repo uses is its own `GITHUB_TOKEN`, and only to read.

**Marker-delimited regions** — Generated content sits between `<!-- agentcfg:start -->` and `<!-- agentcfg:end -->`; anything outside is preserved verbatim. This is the escape hatch for genuinely local content, and what keeps the agent-template's MSRV rationale alive. Markdown only — JSON has no comment syntax and takes the route below.

**emit has no implicit default** — The profile states which emitters it wants; there is no fallback list. `emit: []` is therefore meaningful rather than broken — the manifest deletes everything previously generated, which is the soft off-switch, distinct from `eject`: one leaves the repo with nothing, the other leaves it with the composed files as ordinary content. Because that is a destructive setting reachable by typo, an unknown emitter name is a hard error rather than an empty list — `emit: [agent-md]` must fail loudly, never quietly wipe `.claude/`.

**Generated JSON is owned outright** — JSON has no comments, so `.claude/settings.json` cannot carry a marker region, and a merging emitter could never tell a key it wrote last month from one a person added — drop a permission centrally and it could never be removed anywhere, silently, in the one file that governs what Claude may run unprompted. So the emitter owns the file whole and `check` verifies it byte-for-byte like every other output. Repo-local additions go in the profile as `settings_extra:`, merged last. Not `settings.local.json`, which is the personal gitignored override and no home for committed repo config. The invariant holds either way: every generated file is entirely generated, and `.agentprofile.yml` is the only file in a consumer repo a human writes.

**Manifest file** — `.agentcfg-manifest.json` records every generated path. Without it, dropping a concern from a profile leaves an orphaned rule file that nothing ever deletes.

**Path-scoping strategy** — Claude gets native `paths:` frontmatter. AGENTS.md gets an explicit "read X before touching Y" pointer — portable across all 30 tools, and the pattern the current CLAUDE.md already uses.

**order: in frontmatter** — Not `10-`/`20-` filename prefixes. Order and identity are different things; welding them together means reordering is renaming, and renaming costs `git log --follow` and blame on a rules fragment. Default 0, set explicitly only for `tooling.md` — and honestly weaker than when it was written: substitution means nothing has to be *read* before anything else to be understood, so `order:` now serves readability rather than correctness. Kept because it costs nothing and a composed document still reads better with its command table near the top.

**invocation: is per fragment, not policy** — `invocation: model | user`, default `model`. Revised at Stage 0 from `surface: skill | command | both`: Claude Code has merged commands into skills, a skill shadows a command of the same name so `both` has no correct rendering, and "command" is now just a skill flag. Both values emit `.claude/skills/<name>/SKILL.md`; `user` adds `disable-model-invocation: true`. What the field decides is unchanged — who pulls the trigger. A `model` skill's description is a condition the model tests, so only it runs the gates before concluding a task or traces a rule mid-session, and its description loads every session and counts against the budget. A `user` skill fires only when typed and costs nothing until then. Skills of either kind are slash-invocable, take arguments, and carry `allowed-tools` natively. Neither is universally right, so the fragment declares its own invocation and the emitter obeys, exactly as it does for `scope`.

**Glossary at a conventional path** — `docs/domain/glossary.md`, always that path. A convention rather than a variable, deliberately: the path is identical in every repo, so there is nothing to vary and a fragment can simply name it. Deliberately not in `AGENTS.md`: a real glossary runs 30–100 terms and would spend the always-on budget in every session to serve maybe one in four, degrading adherence to everything else.

**One architecture per repo** — Cardinality 0 or 1, not many — the one axis where that asymmetry with `concerns` is deliberate. Concerns are hazards and stack harmlessly: more caution is never incoherent. Architectures are prescriptions and can contradict — `ddd` says the repository returns current aggregate state, `event-sourced` says rehydrate from a stream, and Claude would get both with no way to arbitrate. Cardinality 1 makes that conflict impossible instead of something review has to catch. If `hexagonal` always travels with `ddd`, it belongs inside `ddd/layers.md`; if it sometimes diverges, write it as its own value and widen the field.

**A generated PR has to stay reviewable** — Two halves of one answer. Every emitted block is labelled with the fragment and version it came from, and every bump PR opens with the release's own fragment-level summary, which Renovate embeds from the GitHub release. Written once per release rather than computed in seventy-five repos — and sufficient, because on a version bump the profile is not changing, so the difference is purely upstream. The other case, "you dropped a concern last week", now surfaces where it belongs: `check` failing in the PR of whoever edited the profile. Without both, the Monday PR is 180 lines of reflowed prose, and by week four it gets merged unread. That failure mode is the normal outcome for generated-code PRs, not a pessimistic one.

**The budget is a gate, not an intention** — The always-on set staying small is the assumption the whole composition rests on — it is why the glossary went to a file and why concerns are path-scoped. Stated in a plan and enforced by nobody, it decays: four fragments added over a year degrade every session in every repo with no one noticing. So `check` measures it and fails past a central threshold, and the fix when it trips is moving content behind `scope: paths`, never deleting a rule. What counts is everything loaded unconditionally, which includes the description line of every model-invocable skill — otherwise the cheapest way to evade the gate would be to move rules into a surface it does not measure. What does not count is what never reaches context: `invocation: user` descriptions, and HTML comment lines, which Claude Code strips. Counting either would push authors toward the wrong choice just to pass the gate.

**Reversible on purpose** — `agentcfg eject` strips the markers, leaves the composed files as ordinary checked-in content, and deletes the profile and manifest. It costs almost nothing to build and it answers the only fair objection to centralising 75 repos — "what if this turns out to be wrong in a year". A repo can leave without a rewrite, which is also what makes adopting it a small decision rather than a large one.

**Substitution yes, control flow never** — One pass of `{{ name }}`, and no `{% if %}`, `{% for %}` or inheritance — a deliberate line, and a revision of the earlier "no templating engine at all". Substitution removes a real defect: without it `core/git-flow.md` has to say "run the repo's full gate command" where it could say `just ci`, and vague guidance is worse guidance. Control flow is the opposite — it would let `language/rust/testing.md` ask what the deployment is, which is precisely the cross-axis coupling the single-axis refactor bought and composition already handles additively. Wanting an `{% if %}` is the diagnosis that content belongs in another fragment; an engine without one forces that conclusion instead of papering over it.

**Variables belong to values, never to repos** — A `values.yml` beside the fragments of each axis value declares what it provides — `language/rust/` says `unit: crate`, `gate_command: just ci`. Repos pick values, never write variables, which is why `vars:` was cut from the profile: a repo restating what `language: rust` already determines is a second copy that eventually disagrees. The gain beyond prose is enforcement — `check` resolves every reference, so a new language value that forgets to define the gate command fails loudly rather than emitting quietly vague rules for months.

**Architecture supplements core** — DDD's build-order rule (domain, then application, then infrastructure) is an *addition* to the ordering rule in `core/execution-order.md`, shipped as part of `ddd/layers.md` — core is never edited to accommodate an axis. Composition makes constraints additive, which is the property control flow in the fragments would have cost us — a conditional in `core/` is how this stops being composition and starts being one big template with branches.

**agent-config is public** — Not incidental — it is what makes "no cross-repo credential" true. A consumer's `GITHUB_TOKEN` is scoped to its own repo and cannot fetch a release from a private sibling — and two paths need exactly that: the `check` gate in each repo's CI, and the `just agentcfg` recipe on a laptop. Private would mean handing both a read credential for a sibling repo. The content is commit format, layering rules and when to open a transaction — conventions, not secrets. Anything that ever is a secret stays in a marker region in the private repo that owns it, never in a shared fragment.

**Non-interactive by default** — A tool that prompts cannot run in a workflow, and the workflow is the primary caller. `init` is the single exception and only on a TTY with something genuinely missing. `sync` never prompts even when it is about to lose something — it errors, because prompting on destruction is how people learn to hit `y`. The corollary is that error messages carry the entire user experience, so they get the polish budget a wizard would otherwise have absorbed.

**Auto-merge is per repo, and it lives in .github** — Three presets — `:agentcfg-automerge-never`, `-patch`, `-minor` — selected by one line in a repo's `renovate.json`, defaulting to no auto-merge when a repo extends only the base preset, so automation is opted into rather than inherited. Not a field in the profile: Renovate opens the PR, so Renovate decides, and a setting the deciding tool cannot read is decoration. 75 repos reviewing a weekly PR by hand ends in rubber-stamping, which is the failure the release-notes summary exists to prevent, while a repo that wants every change read should be able to say so. Majors need no rule at all — the shared preset already holds every major behind `dependencyDashboardApproval`. Which means the version number has to carry meaning for prose, so it does. **Patch**: wording, examples, clarification — no rule changes meaning. **Minor**: a new fragment, value or rule, additive, nothing you were doing becomes wrong. **Major**: a rule reversed or removed, a fragment renamed, or a profile schema change — something you were doing is now wrong, or your profile needs editing. Releases pick one of the three deliberately; that judgement is a step in `/new-value` and the release checklist.

**MIT, like the templates** — agent-config is public and carries the same licence as `claude-mit-*`. Stated rather than assumed, because a public repo without a LICENSE grants nothing and the fragments are meant to be copyable.

**Axes are observed** — An axis earns its existence by being observed across repos, never anticipated. Deployment qualified because all three current repos already differ on it; sensitivity is declared empty because retrofitting it later is the expensive case. Concurrency, protocol and visibility were rejected as derived, or as plain variables two paragraphs reference. Values are the separate and much cheaper question, governed by *central first*.

**Deferred on purpose** — Framework fragments, the Cursor emitter, the plugin marketplace, and `hmi-components`. Each is additive; none is blocked by anything built here. Also the fleet view — which repos are behind on `config_version` — which is a read-only scheduled workflow in agent-config rendering a table into its own README, not a feature of the binary. It is worth nothing at three repos and obvious at thirty.

## What could go wrong

### The spec read moves the emitter design

**Closed at Stage 0.** The AGENTS.md side held: nested-file semantics differ by agent — Codex supplements, Copilot is unspecified, Claude Code reads no AGENTS.md at all — and concern scopes are globs no single nested file can express, so root-level pointers remain the only strategy. What moved was the claude emitter's `surface:` model, revised to `invocation:` before any code depended on it. Detail in `docs/stage-0-spec-read.md`.

### Context budget on the always-on set

Core plus language loads unconditionally in every session, and adherence degrades well before 200 lines. Measure at Stage 3, not at rollout, and from Stage 2 onward `check` holds the line automatically. If it runs long, the fix is moving more content behind `scope: paths` — not trimming the rules.

### Stage 4 leans on one Renovate feature

Reading the implementation rather than the issue titles disposes of most of what was flagged here: post-upgrade changes are collected from `git status`, and untracked files, deletions and renames are each handled explicitly, all filtered through `fileFilters` (default `**/*`). New rule files commit, and orphans the manifest removes commit as deletions.

What is left is narrower. Commands run *without a shell* unless `allowShellExecutorForPostUpgradeCommands` is enabled globally, so the task is a sequence of bare invocations rather than a pipeline, each matching `allowedCommands` after Handlebars compilation — and a miss records an artifact error on the PR rather than passing quietly, which is the failure you want. The task also runs only when the manager actually changed a file, so it can never self-heal drift; that is `check`'s job, not its own.

The real exposure is structural: every repo's agent config now depends on a self-hosted-only feature that executes commands inside the run holding the org-wide token. If that surface changes, or ninoverse moves to Mend-hosted Renovate, Stage 4 gets rebuilt — but only Stage 4. The fragments, the binary, the profile and the check gate are untouched, and the fallback is the per-repo sync workflow this replaced.

### Neutralised prose reading as vague

Largely solved rather than mitigated, now that `{{ gate_command }}` renders to `just ci` in the repo that reads it — the composed output names things instead of gesturing at them. What survives is the residue: a sentence whose *structure* assumes a language, not just its nouns. "Add the crate to the workspace members list" has no Go reading however the noun is substituted, and no variable catches that. It stays an editorial hazard in Stage 1, just a much smaller one.

### Concerns and architecture arguing over the same rule

Both are path-scoped and language-neutral, so a rule can plausibly land in either. The boundary that has to hold: **concerns are hazards of an activity** ("a database is slow, it locks, it N+1s" — true whether or not you do DDD), **architecture is where things may live and what shape they keep**. The pair composes correctly where it matters: data-access says put multiple writes in one transaction, DDD says never write two aggregates at once, and together they say one aggregate, one transaction. Watch for the first rule that genuinely fits both, and write down which axis won and why.

### Concern globs that match nothing

Path-scoped rules silently never fire when globs miss. A repo whose data access lives somewhere unexpected gets no data-access rules and no error. `check` therefore warns on a `paths:` pattern matching zero files (Stage 2). It stays a warning: a repo can legitimately declare a concern before the code that triggers it exists, and a failure there would punish exactly the repos doing it right.

## Glossary

Split by provenance, because it tells you which terms you can look up and which only exist here.

### Coined for this project

**axis** — A dimension a repository varies on — language, framework, architecture, deployment, concerns, sensitivity. An axis holds *values*; a profile picks between them, and how many it may pick is that axis's cardinality. Six exist. Adding one is a field in every profile, a dimension in every emitter test, and a question every new repo must answer, which is why an axis has to be observed across several repos before it exists. `core/` is not an axis: it has no values and is always included.

**agentcfg** — The Rust binary. Reads a profile, selects fragments, runs emitters. It never parses markdown — bodies pass through untouched but for one `{{ name }}` substitution pass — so the work is frontmatter splitting, selection, substitution and emission. Six subcommands: `sync`, `check`, `plan`, `why`, `init`, `eject`.

**always-on budget** — The ceiling on composed `scope: always` content, 200 lines to start, declared centrally and enforced by `check`. Path-scoped fragments do not count against it — they cost only the sessions that touch matching files. It is the constraint that keeps composition honest: without it, every fragment added anywhere is a tax on every session everywhere.

**cardinality** — How many values of one axis a single repo may pick. `language` and `deployment` take exactly one, `framework` and `architecture` none or one, `concerns` any number including none. It is a property of the axis, not of a fragment, and the profile schema enforces it.

**central first** — No repo declares a value that agent-config has not released. It replaces an earlier "a value earns its existence at the second repo", which was over-cautious about values and had an exception it could not survive — `language` and `deployment` are mandatory picks, so their values are always earned by the first repo needing them. Enforced by the tool rather than by memory: valid values are the embedded directory listing. Axes remain guarded separately, because an axis costs at every repo and a value costs only at its own.

**drift check** — `agentcfg check` running in a consumer repo's CI. Recomposes the expected output and exits non-zero if a generated file was hand-edited, or if the always-on set is over budget. This is what makes duplicating bytes into every repo safe rather than a fiction.

**eject** — The exit. Strips the markers, leaves the composed files in place as ordinary checked-in content, removes the profile and manifest. The repo stops being managed and loses nothing. Its purpose is mostly psychological, and none the less real for it: reversibility is what makes adoption a small decision.

**emitter** — Translates selected fragments into one agent's file layout — same bodies, different frontmatter and paths. `agents-md` and `claude` in v1. A new agent is a new emitter, never a content migration.

**fragment** — One markdown file of instructions, the smallest unit — it lives inside exactly one axis value (or inside `core/`). Agent-neutral body; neutral frontmatter carrying `scope` (`always` or `paths`), `title`, `order` where sequence matters, and `invocation` on the task-shaped ones. A repo composes 14 of them today; v1 authors 30 in total.

**manifest** — `.agentcfg-manifest.json` — every path the tool generated in this repo. Without it, dropping a concern from a profile leaves an orphaned rule file that nothing ever deletes.

**marker region** — The span between `<!-- agentcfg:start -->` and `<!-- agentcfg:end -->`. Generated content lives inside; anything outside survives regeneration untouched. The escape hatch for genuinely repo-local content, such as the agent template's measured MSRV rationale.

**profile** — `.agentprofile.yml` — the entire per-repo footprint. Names the repo's coordinate on each axis plus the pinned `config_version`, and drives both the fragment selection and the emitted settings.

**provenance comment** — The label each emitted block opens with — source fragment and the `config_version` that produced it. It answers the question centralising creates: a rule you disagree with is no longer a file in your repo you can edit, it is one of eighteen fragments composed from six axes. The comment makes that traceable in the file itself, makes `why` a lookup, and gives every hunk of the Monday diff a name.

**single-axis refactor** — The Stage 1 editorial pass: rewriting each existing file so it belongs to exactly one axis. It is what removes the crate/package and `just`/`make` vocabulary problem without control flow — the words move into the language value, and the core fragment references them as variables instead of choosing between them.

**values.yml** — The variable declarations of one axis value, sitting beside its fragments. Not a fragment itself — nothing emits it — so it does not count toward the thirty. It is the other half of the single-axis refactor: fragments stop naming a language's vocabulary and reference it, and `check` fails when a value omits something a fragment asks for.

**value** — One option on an axis, and one directory in the tree — `rust` and `go` are values of `language`; `service`, `library` and `template` are values of `deployment`. A value contains fragments. Picking a value is what pulls its fragments into the composition.

### Borrowed from elsewhere

**AGENTS.md** — Open specification released by OpenAI in August 2025 with Google, Cursor and Factory, donated to the Linux Foundation's Agentic AI Foundation in December 2025. Read natively by 30+ agents. The canonical output of this system.

**CLAUDE.md** — Claude Code's own instruction file. Claude Code does not read AGENTS.md, so here this is a two-line `@AGENTS.md` import plus anything genuinely Claude-specific below it.

**.claude/rules/** — Claude Code's rules directory. A file carrying `paths:` frontmatter loads only when Claude touches matching files, which is where framework and concern fragments land for Claude — and how the always-on context budget stays affordable.

**conventional commits** — The `type(scope): subject` format. Load-bearing rather than cosmetic here: `bump-version.yml` reads the subject line to decide whether to cut a release and how far to bump.

**merge gates** — The repos' pre-merge sequence — format check, lint, test, licences and advisories — run in order by `just ci` or `make ci`, and as separate CI jobs so a red build names the gate that broke.

**MSRV** — Minimum supported Rust version. Declared in four places in the agent template — `Cargo.toml`, `clippy.toml`, the Dockerfile and the CI input — and a dedicated job exists to catch a partial bump.

**postUpgradeTasks** — Renovate's hook for running a command after a dependency is updated but before the commit is created — which is what lets a version bump and its regenerated files arrive as one commit. Self-hosted only, and each command must match `allowedCommands`, a global option no repository can set for itself. ninoverse already self-hosts Renovate centrally, which is the only reason this is available.

**reusable workflow** — A GitHub Actions workflow invoked with `uses:` from another repository. How `ninoverse/.github` already centralises CI and versioning, alongside the Renovate preset — the precedent this whole design follows.

---

*Effort figures are working estimates for focused time, not calendar time. Stage 1 is the one that decides whether this succeeds — the tooling is straightforward, the editorial judgement about what is genuinely universal is not.*