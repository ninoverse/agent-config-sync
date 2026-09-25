# agent-config Rollout

Centralising Claude, Codex, Copilot and Cursor instructions for the ninoverse repositories into single-axis fragments, composed per repo by a Rust binary and synced as ordinary committed files. Seven stages, sequenced so nothing is built before the thing it depends on is proven.

**33** fragments in v1 · **~75** repos they compose into · **6** axes, one declared empty · **2** emitters in v1 · **1** new file per consumer repo · **30+** agents reading the output

> **Status:** design settled; all seven stages complete.
> Every decision below was reached deliberately; the *Decisions locked in* section
> exists so they are not relitigated. What is still open is recorded under
> *What could go wrong*, and the direction past coding agents under
> *Beyond coding agents*.
>
> **Where it stands:** four repositories are composed rather than hand-written —
> the three consumers and agent-config itself — each carrying only
> `.agentprofile.yml` plus generated files, each green on `agentcfg check` at 88,
> 89, 88 and 78 of 200 always-on lines, and none of them has gained a workflow
> file. Distribution works end to end: a one-word edit to a core fragment,
> released as `v0.17.4`, reached `claude-mit-rust-template` as a single Renovate
> pull request carrying the bumped pin and the regenerated files in one commit.
> Extending the tree is `/new-value` plus `docs/fragment-authoring.md`.
> `docs/stage-4-preset-handoff.md` records the boundary Stage 4 crossed and is
> now history rather than instructions.
> Stage 0 is recorded in `docs/stage-0-spec-read.md`;
> Stage 1's fragments are in `fragments/`, their format in
> `docs/fragment-authoring.md`, and the account of every source line in
> `docs/extraction-ledger.md`. Stage 2's binary is `crates/agentcfg/`, and the
> profile it reads is specified in `docs/profile-schema.md`. Stage 3 ran both
> against `claude-mit-rust-template` and fixed what the diff turned up.
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
│   └── … 7 fragments
├── language/              ← an axis   pick exactly 1
│   ├── rust/              ← a value   8 fragments inside
│   │   ├── tooling.md     ← a fragment
│   │   └── …
│   └── go/                8 fragments inside
├── architecture/          ← an axis   pick 0 or 1
│   └── ddd/               4 fragments inside
├── deployment/            ← an axis   pick exactly 1
│   ├── service/  library/  tag-only/  cli/
└── concerns/             ← an axis   pick any number
    ├── data-access/  sync/  template/
```

`core/` is not an axis — it has no values and is always included, which is why it has no cardinality. The six real axes each have a cardinality: how many of that axis's values a single repo may name in its profile. Two languages exist, but a repo declares exactly one of them; five concerns will exist, and a repo may declare none, one or all five. That is what the schema enforces:

| Axis | How many values / one repo declares | Values that exist / to choose from | Fragments / per value | Covers |
| --- | --- | --- | --- | --- |
| language | exactly 1 — `language: rust` | rust, go | 8 | Tooling vocabulary, code-review idioms, testing, file naming, permissions, hooks |
| framework | 0 or 1 — `framework: ~` | **none yet** | — | Axum, Dioxus and the rest. The schema accepts the axis; no value is written until a repo needs one. |
| architecture | 0 or 1 — `architecture: ddd` | ddd | 4 | The structural discipline the code commits to: layer dependency direction, aggregate and value-object rules, where repository interfaces live, bounded contexts. Language-neutral. `hexagonal` and `event-sourced` await a repo that needs them — and a repo picks one lane, because two architectures can contradict each other in a way two concerns never can. |
| deployment | exactly 1 — `deployment: service` | service, library, / tag-only, cli | 1 | What a merge deploys and the injected `PORT` for a service; semver, API stability and doc coverage for a library; a tag that deploys nothing for tag-only; exit codes and stream discipline for a cli. |
| concerns | any number, / including none — `concerns: [sync]` | data-access, sync, / template, / fragment-authoring | 1 | Language-neutral. Hazard concerns are path-scoped, so they load only when Claude touches matching files. Two are not hazards: `template`, the always-on rules for a repository others copy, and `fragment-authoring`, which carries `/new-value` and earns its place against *Beyond coding agents*. Heavy-calc and fetching deferred. |
| sensitivity | exactly 1, defaulted — `sensitivity: none` | **none only** | 0 | Payload logging, error-message contents, retention, encryption at rest, audit trail. Declared now because retrofitting it across dozens of repos later is the expensive case. |

So v1 authors **33 fragments** — 7 core, 7 each for rust and go, 4 for `ddd`, 4 across the deployment values, 4 concerns. Each language value also ships a `values.yml` and a `settings.partial.json`, which carry no frontmatter and are therefore files rather than fragments; counting them is what made this number 34 until Stage 6 checked it. At full spread (five languages, a dozen frameworks, five concerns, a handful of architectures) it lands near 70, still serving ~75 repos.

The whole per-repo footprint is one file. This is `claude-mit-rust-agent-template`'s, verbatim, with the two optional axes shown as comments — an unnamed axis is simply absent, which is what "0 or 1" looks like in practice:

```yaml
# .agentprofile.yml
config_version: v0.17.6
language:    rust          # exactly 1
                           # framework:    0 or 1 — no value exists yet
                           # architecture: 0 or 1 — no repo declares one
deployment:  service       # exactly 1
concerns:  [template]    # any number
                           # sensitivity: exactly 1, defaults to none
emit:        [agents-md, claude]
```

That profile composes **17 fragments**: 7 core + 8 rust + 1 deployment + 1 concern. Adding `architecture: ddd` would make it 21 — Stage 5 considered it for this repository and left it off, because the crates carry no domain, application or infrastructure layer for those rules to govern. `claude-mit-rust-template` composes 17 too — same core, same rust, same concern — differing in exactly one fragment, `tag-only/release.md` instead of `service/release.md`. That single fragment is the difference between a stray push to `main` costing a junk tag and a stray push deploying to Cloud Run, which is the clearest argument for deployment being an axis at all.

### Why deployment is an axis and concurrency is not

Deployment is already differentiated across the three existing repos, and it is the axis the bump-version finding below actually turns on: `claude-mit-rust-template` is `tag-only`, with no deploy, the other two are `service` repos wired to Cloud Run. The rules genuinely diverge — a merge that deploys and a server that must honour `PORT` on one side, semver and public-API stability on the other — and neither belongs to language or concern.

Architecture qualified on the same test but by a different route: it has no value in any repo yet, but one value — `ddd` — is a large, coherent, language-neutral body of rules that will be declared by several repos rather than one. That is the reuse ratio an axis has to clear, and a business-domain axis (billing, telemetry) fails it badly: roughly forty values for seventy-five repos is relocation, not centralisation. Domain rules stay in the marker region.

Sensitivity is the opposite case: no content today, but declaring `sensitivity: none` costs one line now and retrofitting the axis across dozens of repos later does not. Concurrency model, protocol and visibility were all considered and rejected — the first two are determined by framework or language, and the third is a variable that two paragraphs reference, not a body of rules.

> **Central first** — No repo declares a value that agent-config has not released. Adding F# is `language/fsharp/`, then a release, then the consuming repo's pin — two PRs in two repos, in that order. Nobody has to remember it: valid values are the embedded directory listing, so `language: fsharp` is a hard error until that directory ships. Axes are the expensive thing and stay guarded — one is a field in every profile, a dimension in every emitter test, and a question every new repo must answer. A value is only a directory, paid for by the repos that name it.

## Stages

Sequenced by dependency, and shaped to the no-stacked-PRs rule in `.agents/execution-order.md`: each stage is one branch, one PR, merged before the next is cut.

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

1. **core/** — seven fragments, vocabulary neutralised: the six `.claude/` files plus `behavior.md` from `CLAUDE.md`.
2. **language/rust/** and **language/go/** — including the new tooling fragment and the permissions/hooks partial.
3. **deployment/service/**, **library/** and **tag-only/** — new content, and the axis all three existing repos already differ on.
4. **architecture/ddd/** — new content, four fragments, and the first axis whose rules reach across every layer of a repo that declares it.
5. **concerns/data-access/**, **concerns/sync/** and **concerns/template/** — two hazard concerns of five, enough to prove the axis carries, plus the template rules all three repos share.
6. **Reconcile drift** found along the way (see the map below).

Draft the fragment-authoring guide (`docs/fragment-authoring.md`) as you go — single-axis discipline, vocabulary neutralisation, what makes something core rather than language. Stage 6 edits it into shape, but the judgement being exercised here is the content, and reconstructing it later is archaeology.

> **Done when** — For each of the three repos, the selected fragments concatenated by hand account for every line currently in its `CLAUDE.md` and `.claude/` — with each omission deliberate and written down in `docs/extraction-ledger.md`.

> **Result** — Landed as four PRs: core and the fragment format; rust and go; deployment, ddd and concerns; drift and accounting. The design moved in four places, each recorded under *Decisions locked in*: a third scope, `on-demand`; the `emit:` filter; template as a concern, with `tag-only` as the deployment that deploys nothing; and `core/behavior.md` from `CLAUDE.md`. The ledger accounts for every line of all three repos' `CLAUDE.md` and `.claude/`.

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
- **Fixtures pin the shape of a composition** under `tests/fixtures/<profile>/` — which files, how each is owned, and the fragments composed into each in order. Not a copy of the composed prose: see *Fixtures pin shape, not prose*.
- **Fragments embedded** in the binary at build time, so `config_version` pins content and code together and can never desync. `--fragments` overrides for local iteration.
- **Substitution is ~30 lines, hand-rolled** — scan for `{{ name }}`, resolve against the selected values, and stop. Hand-rolled rather than minijinja precisely so nobody switches conditionals back on later. An unresolved name is a hard error, never an empty string — silently emitting `run` with nothing after it is the worst failure this system could have — and literal braces need an escape, with a real case waiting in the fragment that documents Renovate's own `{{{newValue}}}` templates.
- **Valid values are the directory listing** — the embed step emits the value set alongside the fragments, so `language: fsharp` becomes legal the moment `language/fsharp/` ships in a release, and is a hard error before that. Never a hand-written enum: that would make every new language a code change and quietly undo the axis design.
- **Provenance on every block** — each emitted span opens with `<!-- language/rust/tooling.md · v1.3.0 -->`. That comment is what turns `why` into a lookup rather than a text search, and what makes the Monday diff readable at the hunk level.
- **Budget measured, not remembered** — `check` reports the composed always-on size — every non-blank, non-comment line that actually renders into `AGENTS.md` and `CLAUDE.md` — and fails past a threshold declared centrally (200 lines to start). Path-scoped content is uncounted, since it is the always-on set that costs every session — but the *descriptions* of model-invocable skills are counted, because those load every session too and would otherwise be spend the gate cannot see. An `invocation: user` skill's description never enters context, so it is uncounted. So are HTML comment lines — markers and provenance — which Claude Code strips before loading; counting them would spend 18 of the 200 lines on the reader that does not need them.
- **Idle rules warn** — a path-scoped rule none of whose globs match anything in the repo is reported by `check`. Per rule, not per pattern, since a concern lists alternatives deliberately. A warning, not a failure: a young repo may legitimately not have that layout yet.
- **A damaged marker region is a hard error** — missing end marker, nested markers, markers out of order. `sync` refuses and leaves the file untouched rather than guessing where generated content ends.
- **`init` detects what it can** — `Cargo.toml` or `go.mod` pre-fills `language`. Everything else is a flag or a default, because everything else is genuinely a choice. It prompts only when stdin is a TTY, and for two different kinds of thing: a required value that is still missing, where `--non-interactive` turns the prompt into a hard failure, and the repository's own overview, where a skip is just a skip. Flags always win, so an agent scaffolding a repo from the template never sees a question.
- **AGENTS.md opens with the repository's own words** — composition supplies rules and never context, so a composed AGENTS.md describes the workflow perfectly and the project not at all. `init` asks for a sentence or two and writes it above the marker region, where `sync` appends below it and never touches it again. Optional in every direction — a blank answer, a pipe and `--non-interactive` all skip — because an overview improves the file rather than being a precondition for composing one. Stage 3 is what found the gap: the pilot's generated AGENTS.md was correct and read like it belonged to no project in particular.
- **`why` ships as a skill too** — the claude emitter writes a model-invocable `/why` next to `/gates` and `/new-crate`. The agent obeying these rules is the one most likely to need to trace one, and mid-session is exactly when the distance to the central repo hurts.
- **The profile schema is written down** — one documented reference for every field, its cardinality, its default and whether it is required. It has accreted across design rather than being specified in one place, and the tool that validates it is the natural home for the document.
- **`sync` never writes `.agentprofile.yml`** — it only reads it. That is a correctness constraint, not a preference: Renovate's custom manager owns that file during a bump, and a post-upgrade task that rewrites a file the manager already changed has its version silently discarded.
- **The claude emitter owns `.claude/settings.json`** — composed from the language value's `settings.partial.json` plus the profile's `settings_extra:`, written whole, verified byte-for-byte. No key-level merge, because JSON cannot carry a marker region.
- **Error messages are the interface** — the tool never prompts, so its failures carry the whole UX. A drift failure names the file, the fragment owning the changed block, and the one command that fixes it. A budget failure lists the always-on fragments with line counts, largest first, so the thing to move behind `scope: paths` is the first line you read.

> **Done when** — `just ci` is green and the golden fixtures cover: rust, go, a two-concern profile, a profile whose concern was removed (proving the manifest deletes the orphaned rule file), an always-on set over budget (proving `check` fails), and a mangled marker region (proving `sync` refuses).

> **Result** — Landed as nine PRs: the crate and fragment model; the profile; selection and substitution; the agents-md emitter; the claude emitter; marker regions and the manifest; `sync` and `plan`; `check` and the budget; `why`, `init` and `eject`. All six subcommands work and 158 tests pass, against stable and against the MSRV. Every fixture in the Done-when is covered except the over-budget one, which is a unit test rather than a fixture — no real profile can reach 200 lines, so it is proved against a synthetic oversized fragment instead.
>
> Thirteen decisions the design did not cover are recorded under *Decisions locked in*, and three of them contradict the letter above: fixtures pin shape rather than prose, the budget counts what renders rather than a formula over fragments, and a glob warning is per rule rather than per pattern. The bullets above have been corrected to match what was built. Measured always-on cost for the three real profiles: 88, 119 and 91 of 200 lines.

### Stage 3 · ~half day — Pilot against `claude-mit-rust-template`

The cleanest of the three — no repo-specific extras to confuse the signal. Run `agentcfg sync --fragments ./fragments` against a local checkout and diff the generated tree against the current `.claude/`.

Then iterate the *fragments*, not the emitter, until every remaining difference is one you intended. This is where Stage 1's editorial work is actually validated; expect to spend most of the half day here, not in code.

> **Done when** — The diff contains only intended changes and `agentcfg check` is green, budget included — Stage 2 measures the always-on set, so this stage does not count lines by hand.

> **Result** — Landed as two PRs: the fragment drift, and the overview `init` now asks for. The pilot's generated tree passes `check` with the always-on set at 88 of 200 lines, and its `.claude/settings.json` parses equal to the template's hand-written copy but for the one line this stage changed on purpose — the keys come out in a different order because the serialiser sorts them, which is deterministic and is what `check` verifies against.
>
> Two fixes, both in fragments and neither in the emitter, which is the whole point of the stage. The `Stop` hook in the rust and go settings partials sent a broken build to `CLAUDE.md`, which after rollout is a two-line `@AGENTS.md` import. And the `new-unit` tasks opened with `` `$name` ``, which binds from the skill frontmatter for Claude and is literal text in `.agents/` — sitting eight lines above `cargo new --lib crates/<name>` in a document that is mostly bash, where an agent resolving it the shell way writes `crates/$name`.
>
> Of the template's 463 distinct non-blank source lines, 102 are not byte-identical in the generated tree, and each one was read: a heading that became a `title:`, a `.claude/` path that became a title in the pointer index, prose rewrapped to a different line width, vocabulary that became `{{ unit }}`, frontmatter the emitter now YAML-quotes, the `$1` argument reference Stage 0 had already found wrong, or a drift resolution recorded in `docs/extraction-ledger.md`. Nothing is unaccounted for, which is the claim that matters; the count itself is a proxy, since moving a line break makes a line differ without changing a word.
>
> One finding was not drift at all: the composed AGENTS.md described the workflow perfectly and the project not at all, because composition supplies rules and never context. That became `init`'s second question and a decision of its own. Two others were looked at and deliberately left. `$ARGUMENTS` reads as an unfilled slot to an agent that cannot bind it, which is what `docs/fragment-authoring.md` chose. And a task body exists twice for Claude — once as a skill, once in `.agents/` — which costs nothing against the budget, is regenerated from one fragment, and is proved identical by `check`; making the index point Claude at the skill instead would mean a second copy of the index inside `CLAUDE.md`, which is more machinery than the context it would save.

### Stage 4 · ~half day — Distribution — the update rides Renovate

Six pieces, and not one of them is a sync workflow in a consumer repository. The central self-hosted Renovate run in `ninoverse/.github` already updates every opted-in repo on a whole-installation App token; agentcfg becomes one more dependency it knows how to bump, which is what removes the per-repo sync workflow entirely.

- **Release workflow** in agent-config — static binaries for linux-musl x86_64/aarch64 and macOS aarch64, attached to a tagged release, plus **generated release notes** listing the fragments added, changed and removed. Renovate embeds release notes for the `github-releases` datasource, so that summary becomes the body of every bump PR in every repo, written once instead of computed seventy-five times. The repo is public, so every download is unauthenticated `curl`.
- **A shared release path in `.github`** — `rust-release.yml`, pinned to a released version and called the way `ci.yml` and `bump-version.yml` already call theirs, generating the conventional-commit changelog every repository wants. It takes one `extra-notes` input, and agent-config fills it with the fragment summary above — prepended, so the section about the rules leads and the tool's own changelog sits beneath it. agent-config's release workflow was written self-contained first, because the preset repo was out of reach; converting it to a caller is what proves the slot.
- **Custom manager in `default.json`** — matches `config_version` in `.agentprofile.yml` against the `github-releases` datasource, the same regex-annotation technique already used for the pinned Renovate version. It needs its own `groupName`: the preset currently folds every minor and patch into one "non-major dependencies" PR, and an agentcfg bump buried among cargo updates is precisely the unreviewable PR this design exists to avoid.
- **`postUpgradeTasks` on that rule** — runs `agentcfg sync` after the pin is bumped and *before the commit is made*, so the new pin and the regenerated files land in one commit and `main` is never inconsistent. `executionMode: branch`, with `allowedCommands` set in `renovate.yml` — a global-only option, so a consumer repository cannot make the central run execute anything. Commands get no shell by default, so this is three bare invocations in sequence — fetch the pinned binary, mark it executable, run `sync` — each matching the allowlist after its template is compiled.
- **Three auto-merge presets in `.github`** — `github>ninoverse/.github:agentcfg-automerge-never`, `-patch`, `-minor`, chosen by a second line in the repo's `renovate.json`. Majors need nothing added: the shared preset already puts every major behind `dependencyDashboardApproval`.
- **`agentcfg check` as a CI gate**, plus the **`just agentcfg` recipe** that fetches the pinned version into a gitignored cache — no global install and no toolchain, since the Go repos have no Rust. Together they cover the other direction: when someone edits their profile to add a concern, `check` fails in their own PR and the fix is one command locally. Better than a bot regenerating it afterwards, because the person making the change sees the result. agent-config runs the same recipe against the *previous* release, which is how it eats its own output without a build loop.

No new schedule either — the central run already fires weekly, on a Monday cron. The window Renovate itself allowed inside that run was `before 6am on monday` when this was written, and narrowing it that far turned out to be the bug: see *A four-hour window is not a schedule*.

Four of those pieces land in `ninoverse/.github`, which a session cannot attach: `add_repo` refuses a repository whose name begins with a dot, because its clone would land at a hidden path. `docs/stage-4-preset-handoff.md` is what a session that does have it reads — the strings that cross the boundary, what each pull request is, and which parts are inference rather than observation about a repository nobody here has opened.

> **Done when** — A deliberate one-word edit to a core fragment, released as a new tag, produces a *single* Renovate PR in the pilot repo carrying both the bumped pin and the regenerated files, its body naming the fragment that changed — and no consumer repository has gained a workflow file.

> **Result** — Landed as seven PRs: five in `ninoverse/.github` — the shared `rust-release.yml`; the custom manager; `postUpgradeTasks` with `allowedCommands`; the three auto-merge presets; and one correcting two things the others turned up — plus two here, converting `release.yml` into a caller and the one-word fragment edit that is the test itself.
>
> The Done-when holds in full. `v0.17.4` changed `core/branch-naming.md` by one word and produced pull request 18 in `claude-mit-rust-template`: one commit, 18 files, the pin and the regenerated tree together, a body opening `**core** · changed — Branch naming`, and all seven checks green including `agentcfg check` — which re-runs `sync` against the new pin, so green means Renovate's regeneration is byte-identical to what the release composes. The pilot has three workflow files, all predating this stage. The handoff's two inferred filenames, `default.json` and `renovate.yml`, were both right.
>
> Four things the build established, all now under *Decisions locked in*: that the preset's schedule gates the pull request rather than the run, which is why pushing `default.json` validates but delivers nothing; that a called workflow can only downgrade the permissions it is handed, so the caller grants `contents: write` or the release 403s after building every target; that the agentcfg `groupName` is load-bearing rather than cosmetic, because branch-mode templating reads the branch's first upgrade; and that `allowedCommands` arrives as JSON5 from the environment, where a wrong escape degrades a regex silently rather than failing.
>
> Both of the first two were found by using the thing rather than reading it — a bump PR predicted and never arriving, and a caller that had to be written. Neither was visible from the design.

### Stage 5 · ~half day — Roll out and decommission

`claude-mit-go-template` first — it validates that the core fragments really are language-neutral, since it is the repo that diverged most.

Then `claude-mit-rust-agent-template`, which is the interesting one: it carries the only genuinely local content in the set (the measured MSRV rationale naming `clap` and the `icu_*` chain, the extra `panic_in_result_fn` allow, the reusable-workflow reference). It proves the escape hatch.

Each rollout PR deletes that repo's old `.claude/*.md` in the same commit that adds the generated tree, so no window exists where both are live and disagreeing.

A rollout is larger than adding a profile, which the first one established. Five things ride along every time: the `agentcfg check` job, which goes *inside* that repo's existing `ci.yml` so no consumer gains a workflow file; `.agentcfg/` in its `.gitignore`, without which Renovate commits a three-megabyte binary into a pull request about prose; the fetch recipe, which is `make agentcfg` in the Go repository since it has no `just`; the cross-references deleting the rule files orphans — see *Adoption orphans what points at the old files*; and stripping the hand-written `CLAUDE.md` above the region `sync` appends, which is the one step every automated check passes without — see *A pre-existing file is not replaced*.

> **Done when** — All three repos carry only `.agentprofile.yml` plus generated files, `agentcfg check` is green in each, and the agent-template's local content survived regeneration untouched.

> **Result** — Landed as two PRs, one per repository. All three consumers now carry only `.agentprofile.yml` plus generated files, `check` is green in each — 88, 89 and 88 of 200 always-on lines — and no consumer has gained a workflow file. The agent template's MSRV rationale survived: it sits below the marker region at the foot of `.agents/rust-testing.md`, and a full `sync` was run afterwards and left it alone.
>
> The Go rollout was the language-neutrality test, and the core fragments passed it. Nothing Rust survived into the composition — no vocabulary, and no sentence whose *structure* assumes Rust with Go nouns substituted in. One imprecision did surface, in the template concern rather than in core: it says the toolchain fails on an empty `{{ unit_container }}`, which is exactly true of a cargo workspace and not of a Go module, where `go build` succeeds and it is `vet` and `test` that fail on matching no packages. The conclusion an agent draws is unchanged, so it is wording rather than a rule, and it is fixed as its own patch.
>
> The escape hatch is narrower than this plan claimed. Of the three things listed above as the agent template's local content, only the MSRV rationale ever was: its clippy lints are byte-identical to the Rust template's, so the `panic_in_result_fn` allow is not extra and the composed crate workflow already carries it, and the reusable-workflow sentence is in the fragment verbatim because every repository calls `rust-ci.yml`. One genuinely local passage across three repositories — which is the number that makes centralising worth doing, and still not zero.
>
> Two things join *Decisions locked in*: that `sync` cannot strip a hand-written file it did not write, and that the fetch recipe depends on a `justfile` setting the first rollout happened to have.

### Stage 6 · ~half day — Close the loop — agent-config adopts itself

The stage that decides whether this survives a year of nobody touching it. Everything before produces configuration for other repositories; this one makes agent-config an ordinary consumer of its own output and writes down how to extend it.

- **agent-config gets a profile** — `language: rust`, `deployment: cli`, `concerns: [fragment-authoring]`. Which means writing `deployment/cli/conventions.md`, the value no repo needed until now: what a merge releases, then exit codes, stdout versus stderr, `--help` quality, and the non-interactive rule this plan already locked. Its own `AGENTS.md` is composed rather than hand-written, with the repository's own overview above the marker region; the authoring guide stays a document in `docs/`.
- **`/new-value <axis> <name>`** — a numbered checklist in the shape of the existing `/new-crate`: create the directory, write the fragments that axis's other values carry, declare the vocabulary a `language` value owes, add a golden fixture, run the gates and the budget check, commit as `feat` so the release is minor, then move the consumer's pin. Adding F# becomes a command instead of an archaeology exercise, and the same command serves a new concern or architecture.
- **The fragment-authoring guide** — drafted during Stage 1 while the editorial judgement is actually being made, edited into shape here. Single-axis discipline, vocabulary neutralisation, core versus language, choosing `scope`, the always-on budget, and the profile schema reference from Stage 2.

> **Done when** — `agentcfg check` is green against agent-config itself, and someone who has never seen the repo can add a language value working only from `/new-value` and the guide.

> **Result** — Landed as four PRs: the two new values with a golden fixture; the adoption; the authoring guide; and this note. `check` is green against agent-config at 78 of 200 always-on lines — the lowest of the four managed repositories, since it declares no `template` concern and `cli` carries one fragment. Its `.claude/` is four skills and `settings.json`; the eleven hand-written rule files are gone, every one of them diffed against its composed counterpart first, and the single line with no counterpart was a claim that a breaking change bumps `Cargo.toml` by hand, which `bump-version.yml` had already made false.
>
> The second half of the Done-when was worked rather than asserted. Walking `/new-value language fsharp` against the shipped checklist found three holes in the guide — no account of what a value actually contains, no mention of `settings.partial.json` anywhere including the layout diagram, and the always-on budget as a parenthetical rather than a section — plus two pieces of guidance that had gone stale against Stage 3, still recommending the `$name` binding that stage removed for rendering as literal text above a bash block.
>
> Three decisions join *Decisions locked in*, and all three are consequences of this repository being the publisher rather than an ordinary consumer: a deployment value has to say what a merge sets off, which is why the cli fragment carries one item more than the bullet above listed; adoption means pinning rather than tracking, which is what separates it from a build loop; and a repository that publishes what it consumes ratchets its own version forever unless it opts out of its own bump. The last was found by asking before merging rather than by merging, and it was the only thing in this stage that would have been expensive to discover later.
>
> Three counts in this document were wrong and are corrected above: the fragment total was 34 because it counted two files that carry no frontmatter, `tooling.md` is `order: -1` rather than `order: 0`, and the concerns axis has gained a fourth value.

## Beyond coding agents

A direction rather than a stage, recorded because Stage 6 adds a value that only
makes sense against it. Nothing here is committed and none of it is blocked by
anything built so far.

**The machinery is already general.** Nothing in `agentcfg` knows what `rust`
means: valid values are a directory listing, substitution resolves names against
whatever the selected values declare, emitters translate a file layout, and the
budget counts lines. A `tone` axis, or a `research` value, composes today with no
code change. That is a property of the single-axis design rather than luck, and
it is why extending to agents that do not write code is a content question and
not a rewrite.

**What is not general is `core/`.** It is the one directory with no cardinality —
always included, nothing to pick — and six of its seven fragments assume a git
repository with branches, pull requests and merge gates:

| fragment | lines about git or PRs | lines about code |
| --- | --- | --- |
| `git-flow.md` | 44 | 2 |
| `execution-order.md` | 15 | 13 |
| `pr-guidelines.md` | 13 | 2 |
| `commit-conventions.md` | 10 | 5 |
| `branch-naming.md` | 5 | 1 |
| `code-review.md` | 1 | 6 |
| `behavior.md` | 0 | 7 |

Only `behavior.md` is close to agent-general — think before acting, simplicity
first, surgical changes, goal-driven — and it still says *codebase*. A research
or support agent inherits none of the rest.

**The vocabulary contract points the same way.** Core fragments make 35
`{{ name }}` references across 12 distinct names — `unit` 11 times,
`gate_command` 3, `unit_container` 3 — and *every one* is supplied by a language
value. `language` is cardinality exactly 1, and an unresolved name is a hard
error by design, so a profile without a language does not degrade gracefully; it
fails to compose. Dropping the axis for non-coding agents is therefore not a
one-line change.

**Two shapes would work.** Split `core/` into a genuinely universal remainder
plus a new axis — `domain`, cardinality exactly 1 — whose `code` value carries
git flow, branch naming, commits, PRs, execution order and review, leaving
`research`, `support` and `ops` as siblings; `language` then becomes 0 or 1,
meaningful only under `domain: code`. Or make `core/` itself that axis,
defaulting to `code`, which reads worse but moves less. Either is a **v2 schema
change**: every existing profile gains a required field, so `config_version`
goes major and every consumer edits one line. That cost is the reason this is a
direction and not a stage.

**Same repository or a separate project is not yet decidable, and does not have
to be.** The fragments and the binary are shared either way; the real fork is
whether one `fragments/` tree serves both domains or two trees share one tool.
One tree is simpler to operate and means a non-coding consumer pins releases
mostly about Rust and Go. Two trees give independent release cadence and make
`agentcfg` a published tool in its own right, with the versioning and support
that implies. The answer follows from whether the second domain's fragments
turn out to share anything with the first — which is knowable only once some
exist.

**What Stage 6 does about it, and what it does not.** It adds
`concerns/fragment-authoring/`, holding the `/new-value` checklist. Under
today's tree that is a value with one consumer, which *central first* would
normally refuse. It earns its place against this section: a repository that
authors agent configuration is a category rather than a description of this one,
and the category has members the moment a second domain exists. Nothing else
here is built, and the axes below are unchanged.

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
| core | behavior.md | CLAUDE.md | **byte-identical in all three** The Behavioral Guidelines block, plus the "Maintain the Build" rule. `scope: always`. Added in Stage 1: `CLAUDE.md` becomes an `@AGENTS.md` import, so its content needs fragments too. |
| language | tooling.md + values.yml **order: -1** | CLAUDE.md **Commands & Tooling** | The command table and the workspace or module rules from `CLAUDE.md`, plus the `values.yml` declaring unit noun, gate command and formatter for every core fragment to reference. `order: -1` is now presentation — substitution means nothing depends on reading it first, and it leads only because a composed document reads better with its command table near the top. |
| language | code-review.md | code-review.md | The unwrap/expect ban and unsafe policy for Rust; the errcheck and wrapping rules for Go. Genuinely different rules, not different words. |
| language | testing.md | testing-requirements.md | The one file that already differs between the two Rust repos. The agent-template's extra MSRV rationale goes to its local region, not here. |
| language | file-naming.md | file-naming.md | **~95% language-specific** Layout and naming tables throughout. Goes entirely to language — no core half worth extracting. |
| language | tasks/new-unit.md | crate-workflow.md / package-workflow.md | Task-shaped, `invocation: model`. Emitted into AGENTS.md as a pointer and as `.claude/skills/` for Claude — model-invocable because "add a crate" said in prose should run the nine steps, which a user-only skill never sees. Takes a named `arguments:` list rather than `$1` — see the drift note below. |
| language | tasks/gates.md | commands/gates.md | Same treatment as above. |
| language | settings.partial.json | .claude/settings.json | Permission allowlist plus the formatter and build-check hooks. Claude-only, merged by the claude emitter. |
| language | automation.md | CLAUDE.md **Automation** | `emit: [claude]`. What the settings hooks do — format on edit, check the build at turn end — and so what Claude need not do by hand. Added in Stage 1: true for Claude Code, wrong for every agent reading AGENTS.md. |
| architecture | ddd/layers.md | new | `scope: always`. The layer model and dependency direction — the domain layer imports nothing. Also carries the build-order supplement: domain unit first, then application, then infrastructure. |
| architecture | ddd/domain-model.md | new | `paths: **/domain/**`. Entities, value objects, aggregates. Immutability and value equality; the aggregate as transaction boundary; reference other aggregates by ID, never by pointer. Naming goes through the glossary: check it before introducing or renaming a type, and add the term in the same commit. This fragment carries the enforcement because it is the one already scoped to the domain layer. |
| architecture | ddd/repositories.md | new | `paths: **/repository/**, **/infrastructure/**`. The interface lives in the domain, the implementation in infrastructure; it returns aggregates, never rows, and no persistence type crosses back. |
| architecture | ddd/boundaries.md | new | `scope: always`. Bounded contexts, ubiquitous language, and an anti-corruption layer at every external boundary. Also fixes the **glossary convention**: every context keeps its ubiquitous language at `docs/domain/glossary.md`, a plain doc a domain expert can read and correct. Types carry their own definition as a doc comment — that copy cannot drift; the glossary covers everything that is not a type, plus the synonyms this context deliberately rejects. Never centralised: a glossary shared across contexts is the universal-`Customer` mistake in new clothes. |
| deployment | service/release.md | new | What a merge to `main` actually costs when the tag deploys to Cloud Run, the injected `PORT`, and a service that is public by default. Shares its trigger with *Git flow*. Graceful shutdown and health checks wait until a service implements them. |
| deployment | library/api-stability.md | new | Semver discipline, public-API stability, deprecation path, doc coverage on exported items. |
| deployment | tag-only/release.md | new | The tag is a marker rather than a release: nothing deploys. The plan's `template` value, renamed in Stage 1 when the template rules became a concern. |
| deployment | cli/conventions.md | new | Written at Stage 6, because agent-config is itself a CLI and becomes the first repo to declare the value. What the tag ships, then exit codes, stdout versus stderr, `--help` quality, and the non-interactive rule. Shares its trigger with *Git flow*, which is what makes the release half reachable. |
| concerns | data-access/rules.md | new | Language-neutral, `scope: paths`. Transactions, N+1, forward-only migrations, lock discipline. |
| concerns | sync/rules.md | new | Idempotency keys, ordering guarantees, at-least-once semantics, conflict resolution. |
| concerns | fragment-authoring/tasks/new-value.md | new | Task-shaped, `invocation: model`. The checklist for adding a value to an axis — the half of Stage 6's Done-when that is not the guide. One consumer today, which *central first* would normally refuse; it earns its place against *Beyond coding agents*. |
| concerns | template/rules.md | READMEs, placeholder docs | `scope: always`. Keep the example minimal, no real business logic, placeholders removed only once real code covers them, and a copy drops the concern from its profile. This is what all three current repos actually are. |
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

**AGENTS.md canonical** — Primary artifact, not a fallback. `CLAUDE.md` is a two-line `@AGENTS.md` adapter, plus any `emit: [claude]` fragments below it. If an emitter breaks, every agent still reads AGENTS.md and nothing is lost.

**Embedded fragments** — Compiled into the binary, so one downloaded artifact is the whole contract and `config_version` pins content and code atomically. A fragment edit therefore requires a release — which is correct, not a cost.

**No new credential** — Corrects an earlier reading of this. The plan first argued for repo-self-sync because a central push "would need an App with write access to every repo" — but that App already exists: the self-hosted Renovate run in `ninoverse/.github` holds a whole-installation token and is already the org's answer to "a central thing changed, update every repo". agentcfg introduces no credential of its own, it becomes another dependency that mechanism already knows how to bump. The blast radius does not widen either, because `allowedCommands` is global-only: a consumer repo cannot make the central run execute anything. The only token a consumer repo uses is its own `GITHUB_TOKEN`, and only to read.

**Marker-delimited regions** — Generated content sits between `<!-- agentcfg:start -->` and `<!-- agentcfg:end -->`; anything outside is preserved verbatim. This is the escape hatch for genuinely local content, and what keeps the agent-template's MSRV rationale alive. Markdown only — JSON has no comment syntax and takes the route below.

**emit has no implicit default** — The profile states which emitters it wants; there is no fallback list. `emit: []` is therefore meaningful rather than broken — the manifest deletes everything previously generated, which is the soft off-switch, distinct from `eject`: one leaves the repo with nothing, the other leaves it with the composed files as ordinary content. Because that is a destructive setting reachable by typo, an unknown emitter name is a hard error rather than an empty list — `emit: [agent-md]` must fail loudly, never quietly wipe `.claude/`.

**Agent-specific content is a fragment filter** — A fragment may declare `emit: [claude]`, and only the emitters it names receive it; the default is every emitter the profile selects. Added in Stage 1 for `CLAUDE.md`'s *Automation* paragraph, which says formatting runs on every edit so the formatter need not be run by hand — true for Claude Code, whose `.claude/settings.json` holds the hook, and wrong for every agent reading AGENTS.md. The claude emitter writes such a fragment below `CLAUDE.md`'s `@AGENTS.md` import, and it counts only against Claude's budget. Attributing the sentence to Claude inside AGENTS.md was the alternative, rejected so that no agent reads rules that do not apply to it.

**Generated JSON is owned outright** — JSON has no comments, so `.claude/settings.json` cannot carry a marker region, and a merging emitter could never tell a key it wrote last month from one a person added — drop a permission centrally and it could never be removed anywhere, silently, in the one file that governs what Claude may run unprompted. So the emitter owns the file whole and `check` verifies it byte-for-byte like every other output. Repo-local additions go in the profile as `settings_extra:`, merged last. Not `settings.local.json`, which is the personal gitignored override and no home for committed repo config. The invariant holds either way: every generated file is entirely generated, and `.agentprofile.yml` is the only file in a consumer repo a human writes.

**Manifest file** — `.agentcfg-manifest.json` records every generated path. Without it, dropping a concern from a profile leaves an orphaned rule file that nothing ever deletes.

**Path-scoping strategy** — Claude gets native `paths:` frontmatter. AGENTS.md gets an explicit "read X before touching Y" pointer — portable across all 30 tools, and the pattern the current CLAUDE.md already uses.

**Three scopes, not two** — `always`, `on-demand` and `paths`. Added in Stage 1, because none of the source repos loads its rules every session: `CLAUDE.md` is always-on and points at `.claude/*.md` by activity ("Committing code: read …"). Git flow and commit conventions have no path to scope to, and loading them every session would put core alone at 295 lines against a 200-line budget. An `on-demand` fragment declares `when:`; AGENTS.md carries one index line per trigger, the body goes to its own file every agent can read, and only the index line counts against the budget. The index replaces the hand-written *Extended Rules* list all three repos keep today.

**order: in frontmatter** — Not `10-`/`20-` filename prefixes. Order and identity are different things; welding them together means reordering is renaming, and renaming costs `git log --follow` and blame on a rules fragment. Default 0, set explicitly only for `tooling.md` and for `git-flow.md`, whose index line says to read it first — and honestly weaker than when it was written: substitution means nothing has to be *read* before anything else to be understood, so `order:` now serves readability rather than correctness. Kept because it costs nothing and a composed document still reads better with its command table near the top.

**invocation: is per fragment, not policy** — `invocation: model | user`, default `model`. Revised at Stage 0 from `surface: skill | command | both`: Claude Code has merged commands into skills, a skill shadows a command of the same name so `both` has no correct rendering, and "command" is now just a skill flag. Both values emit `.claude/skills/<name>/SKILL.md`; `user` adds `disable-model-invocation: true`. What the field decides is unchanged — who pulls the trigger. A `model` skill's description is a condition the model tests, so only it runs the gates before concluding a task or traces a rule mid-session, and its description loads every session and counts against the budget. A `user` skill fires only when typed and costs nothing until then. Skills of either kind are slash-invocable, take arguments, and carry `allowed-tools` natively. Neither is universally right, so the fragment declares its own invocation and the emitter obeys, exactly as it does for `scope`.

**Where a rule's body lands** — Added in Stage 2. Non-always bodies go to `.agents/<name>.md`, named from the fragment's *source path* rather than its file stem: three fragments in the tree are called `rules.md` and `concerns` is the axis a repo may pick several values of, so `data-access/rules.md` and `sync/rules.md` would land on one file and lose one of them silently. `core/` keeps its bare stem, a value contributes its own name (`data-access-rules.md`, `ddd-domain-model.md`), and a task uses its skill name, so the pointer an agent follows and the skill Claude runs carry the same word. Keyed on path, not title, so retitling a fragment is never a rename and `git log --follow` keeps working. A naming scheme is still a weak guarantee, so every emitter also rejects two files claiming one path.

**A file that leads with generated frontmatter is owned whole** — Added in Stage 2, correcting *Generated JSON is owned outright*, which said "JSON" where it meant this. `.claude/rules/*.md` and `SKILL.md` are markdown, but a marker comment cannot sit above the frontmatter that makes them work, and putting the frontmatter outside the region would let a hand-edited `paths:` survive regeneration and drift unnoticed. They are written whole and verified byte-for-byte. `AGENTS.md`, `CLAUDE.md` and the `.agents/` files keep their regions, which is where genuinely local content lives.

**Path-scoped rules are written twice, deliberately** — Added in Stage 2. One fragment, two renderings: `.claude/rules/<name>.md` with native `paths:` frontmatter, and `.agents/<name>.md` with none, pointed at from AGENTS.md. Writing it once was considered and rejected both ways: a Claude stub pointing at the neutral file turns an automatic mechanism into one the model must choose to follow, and an AGENTS.md pointer into `.claude/` makes the canonical artifact depend on a Claude-specific directory. `emit:` admits any subset, so each emitter has to be self-sufficient. The usual objection to duplication does not apply — neither copy is hand-maintained, both are regenerated from one fragment, and `check` proves they cannot diverge.

**`claude` cannot be emitted without `agents-md`** — Added in Stage 2, enforced by the profile schema. `CLAUDE.md` is an `@AGENTS.md` import and the AGENTS.md index is what points Claude at the rules it reads on demand, so a claude-only profile would import a file nobody wrote and follow every pointer into nothing. `agents-md` alone stays valid — that is what AGENTS.md being canonical rather than a fallback means.

**Sensitivity ships an empty value, not a special case** — Added in Stage 2. The axis was declared with no rules and no directory, which the directory-listing rule would have rejected. `fragments/sensitivity/none/` now exists and holds nothing, so `sensitivity: none` validates the way every other axis does and filling the axis in later means adding files rather than editing a validator. Hardcoding `none` in the validator was the alternative, and it is exactly the hand-written value the design exists to avoid. The axis sorts last in the composition order, after `concerns`, matching the axis table above.

**One name, one value** — Added in Stage 2. Two selected values declaring the same variable is an error, not a precedence rule: which value wins would be an invisible rule, and failing is not. Unreachable from today's tree, where only language values declare vocabulary and cardinality is one, so it is proved against a tree written for the purpose.

**Provenance stamps the binary, not the profile** — Added in Stage 2. Each block opens with the version of the binary that wrote it, since a release pins content and code together. A profile whose `config_version` disagrees is a hard error: composing under the wrong binary would stamp provenance nobody could resolve. Under `--fragments` the stamp is `local` and the mismatch drops to a note, because a fragment directory is pinned by no release and iterating on one should not require bumping a pin.

**`settings_extra` merges deeply, and last** — Added in Stage 2. Objects combine key by key, so adding `env:` leaves `permissions:` alone; anything else replaces, so a repo can shorten an array as well as extend it. Composed after every selected value's `settings.partial.json` — generalised from "the language value's", which is simply the only axis shipping one today. Keys come out sorted, a property of the serialiser rather than a choice; what matters is that it is deterministic, because the file is verified byte-for-byte.

**Fixtures pin shape, not prose** — Added in Stage 2, replacing full golden trees. A fixture records which files a profile composes, how each is owned, and the fragments composed into each in order — read back out of the provenance comments. It does not copy the composed text. Duplicating a fragment's prose into three fixtures meant every wording change failed the suite for a reason unrelated to the crate being broken, and the fix was to regenerate rather than to think; 3,647 lines of expected trees became 123. Editing a fragment body, a title or a value's vocabulary now moves no fixture at all, and a fixture fails only on a structural change — which is when someone should look. Content correctness lives in behavioural tests: pointers resolving, no frontmatter leaking, provenance on every block, marker idempotency, orphan deletion.

**The budget counts what renders** — Added in Stage 2, and a correction to the arithmetic above rather than to its intent. The formula — bodies plus one index line per trigger — omitted the index's own heading, intro and section labels, and the pointer line for every path-scoped rule: nine to twelve lines that load every session regardless. So `check` counts every non-blank, non-comment line of the generated regions of `AGENTS.md` and `CLAUDE.md`, plus one per model-invocable skill description, read from the emitted skills so a skill the emitter builds in (`/why`) is measured like any other. That is the stated intent — everything loaded unconditionally, so no surface escapes measurement. HTML comments and `invocation: user` descriptions stay uncounted, because neither reaches a session.

**A glob warning is per rule, not per pattern** — Added in Stage 2. A concern lists alternatives deliberately — data access might live under `store/`, `db/` or `repository/` — and the rule fires if any one matches, so reporting each miss put eleven warnings on a perfectly healthy repository, and a warning that always appears is one nobody reads. `check` reports a rule none of whose patterns match. Build output, `node_modules`, `vendor` and dotted directories are not searched: a compiled artifact should not retire a warning the source tree has not earned, and walking `target/` alone can cost more than the rest of the check.

**Two exits, and they are not the same** — Recorded at Stage 2, since they are easy to mistake for each other. `eject` keeps every composed file as ordinary content and stops managing the repo. `emit: []` plus `sync` deletes the composed files and leaves the repo managed, so naming the emitters again brings them all back — and it goes through the orphan path, which refuses rather than deleting a file someone has written in. Only one combination has no single command: delete the files *and* stop being managed, which is `emit: []`, `sync`, then removing two files by hand. Rare enough not to earn a seventh command, and a seventh would have to re-implement a guard `sync` already provides. `eject` names the other door in its output and its help, since the command line mentions it nowhere else.

**The dependency floor is the MSRV** — Added in Stage 2. `serde`, `serde_json`, `serde_yaml_ng`, `clap`, `globset` and `thiserror`, with the fragment embed hand-rolled in `build.rs` rather than taking `include_dir` — which also lets the embed emit the value listing in the same pass. `globset` is required as `"0.4"` rather than pinned, because 0.4.20 needs Rust 1.88 and the MSRV-aware resolver picks 0.4.19 by itself, so a later update cannot quietly raise the floor. `deny.toml` gained `Unicode-3.0` for `unicode-ident`, which reaches the tree through `syn`; the list already accepted `Unicode-DFS-2016`, so it is the same policy at a newer licence version.

**Glossary at a conventional path** — `docs/domain/glossary.md`, always that path. A convention rather than a variable, deliberately: the path is identical in every repo, so there is nothing to vary and a fragment can simply name it. Deliberately not in `AGENTS.md`: a real glossary runs 30–100 terms and would spend the always-on budget in every session to serve maybe one in four, degrading adherence to everything else.

**One architecture per repo** — Cardinality 0 or 1, not many — the one axis where that asymmetry with `concerns` is deliberate. Concerns are hazards and stack harmlessly: more caution is never incoherent. Architectures are prescriptions and can contradict — `ddd` says the repository returns current aggregate state, `event-sourced` says rehydrate from a stream, and Claude would get both with no way to arbitrate. Cardinality 1 makes that conflict impossible instead of something review has to catch. If `hexagonal` always travels with `ddd`, it belongs inside `ddd/layers.md`; if it sometimes diverges, write it as its own value and widen the field.

**Template is a concern, not a deployment** — Added in Stage 1. All three source repos are GitHub templates, but two of them deploy to Cloud Run on every tag, so their deployment is `service`, and deployment takes exactly one value. The rules for being a template — keep the example minimal, keep placeholders until real code covers them, drop the concern in a copy — hold whether or not the tag deploys, so they live in `concerns/template/`, which all three declare. It is the one concern that is not path-scoped, because it is about the whole repository rather than an activity in some of its files. The deployment value that deploys nothing was renamed from `template` to `tag-only`, so a profile never uses one word for two things.

**A generated PR has to stay reviewable** — Two halves of one answer. Every emitted block is labelled with the fragment and version it came from, and every bump PR opens with the release's own fragment-level summary, which Renovate embeds from the GitHub release. Written once per release rather than computed in seventy-five repos — and sufficient, because on a version bump the profile is not changing, so the difference is purely upstream. The other case, "you dropped a concern last week", now surfaces where it belongs: `check` failing in the PR of whoever edited the profile. Without both, the Monday PR is 180 lines of reflowed prose, and by week four it gets merged unread. That failure mode is the normal outcome for generated-code PRs, not a pessimistic one.

**A shared release path with one slot** — Added in Stage 4. The release workflow moves to `ninoverse/.github` as `rust-release.yml`, pinned to a released version like every other workflow in these repositories, and generates the conventional-commit changelog centrally. What it cannot generate is what a repository knows about itself, so it takes an `extra-notes` input: markdown the caller computes in a job of its own and passes through `$GITHUB_OUTPUT`. agent-config fills it with `agentcfg notes`; a repository with nothing to add omits the job and gets the changelog alone. An input rather than a script the shared workflow runs out of the caller repo — the same reasoning that keeps `allowedCommands` global-only, since a shared workflow executing repo-supplied code inside the run holding the org token widens the blast radius to every repository at once. Prepended rather than appended, because Renovate embeds the whole body in seventy-five bump PRs and the rules are what a consumer is reading for.

**Adoption orphans what points at the old files** — Added in Stage 4, found by the first rollout rather than anticipated. Deleting the nine `.claude/*.md` files left thirty references to them in files agentcfg does not manage: a README table listing all nine, six links in `CONTRIBUTING.md`, three in the pull request template, two lint comments in `Cargo.toml`, four justfile comments, and `CODEOWNERS`, which guarded `/.claude/` as "the product here". They belong in the rollout commit rather than a follow-up — a repository whose README cites deleted files is not adopted, it is half adopted. Most are path swaps. A table listing the rule files is not: it describes a structure that no longer exists, and what replaces it is a short account of the composed one, plus how to trace a rule, change it for everyone, or override it locally. `CODEOWNERS` gains `.agentprofile.yml`, which is what decides the whole tree now.

**The notes diff the source, not the output** — Added in Stage 4. `agentcfg notes` compares two fragment trees, so a release that changed only the binary lists nothing — and says where a change could still have come from, because the tool is an input too: v0.12.0 to v0.13.0 changed no fragment and still added `.claude/skills/why/SKILL.md` to every Claude repository. Diffing the *composed output* instead would enumerate that, and is the better measure: it is what a repository actually experiences, and it subsumes the fragment diff, since a changed fragment shows up as changed output. It is also a different command, needing the previous release's binary at hand rather than just its tree, so it stays a decision to take deliberately. The notes point a reader at the diff; they do not replace reading it.

**The fetch is not checksum-verified** — Added in Stage 4, deliberately. `just agentcfg` downloads over HTTPS from the same origin that publishes `SHA256SUMS`, so a checksum fetched from there proves nothing an attacker able to alter the binary could not also alter. What it would catch is a truncated download, and `curl -f` already covers the common failures. Worth adding the day a corrupt fetch actually happens, and not before.

**The schedule gates the pull request, not the run** — Added in Stage 4, found by predicting a bump PR that never arrived. Renovate evaluates `schedule:` when a branch would be created rather than when the run fires, so the push trigger on `default.json` validates the config immediately and opens nothing outside the Monday window. Both halves matter: a broken preset still surfaces within a minute of the push, which is what that trigger is for, and a correct one still waits, which is what the cadence floor is for. Pulling one update forward is the *Awaiting Schedule* checkbox on the consuming repository's Dependency Dashboard — deliberately in the repository that receives the change rather than in the preset. That reading was right and incomplete: the same symptom had a second cause, found three weeks later and recorded below. A run inside the window opens pull requests; the window was too narrow for a run to land in it.

**A called workflow can only downgrade permissions** — Added in Stage 4. `rust-release.yml` is the first reusable workflow here that needs `contents: write`, and a called workflow's request is capped by whatever the calling job grants rather than added to it. So the caller declares `contents: write` on the job that calls it, and a workflow-level `contents: read` above that is fine, since a job-level block replaces the default rather than being capped by it. Getting this wrong is expensive and late: the run builds every target and then fails the publish. The caller examples in `.github` carry the block for that reason.

**The agentcfg group is load-bearing, not cosmetic** — Added in Stage 4. With `executionMode: branch` Renovate compiles the post-upgrade command against the branch config, which `generateBranchConfig` builds by flattening the branch's *first* upgrade. `{{{newValue}}}` therefore resolves to whatever that upgrade is. Because agentcfg has a group to itself the branch holds nothing else and the answer is unambiguous; folded into the weekly non-major group, the first upgrade could be any cargo crate and the download URL would carry that crate's version. The group was added to keep the pull request reviewable and turns out to be required for correctness too.

**`allowedCommands` is JSON5 from the environment** — Added in Stage 4. Renovate parses an array-typed variable as JSON5 before falling back to splitting on commas, so the patterns are a JSON array in `renovate.yml` and their backslashes are doubled. The escaping is load-bearing in a way that fails quietly: a single backslash makes the JSON invalid, and a `\+` that loses its escape stops being a literal plus and becomes a quantifier, so the pattern silently stops matching `chmod +x` and the task is refused rather than erroring. Also, the patterns are matched unanchored against the compiled command, so each one anchors itself.

**A pre-existing file is not replaced** — Added in Stage 5, and the one rollout step every automated check passes without. `sync` preserves whatever sits outside its markers, which is what makes the escape hatch work; the cost is that a hand-written `CLAUDE.md` with no markers is preserved too, and `sync` appends its region *below* it. Both rollouts came out with a hundred-odd lines of superseded rules sitting above a correct generated region, and `check` was green in both cases, because the region matched. Nothing detects this: the file is well-formed, the composition is right, and the repository simply carries two sets of rules, the stale one first. Adoption has to delete the old content by hand, and a rollout is not done until someone has read the file rather than the check output.

**The fetch recipe needs `set positional-arguments`** — Added in Stage 5. A `just` shebang recipe receives its parameters as `"$@"` only when the justfile sets it, and the recipe is copied between repositories as a block that looks self-contained. Without the setting `just agentcfg check` runs `agentcfg` with no subcommand: it prints help and exits 2, which reads like a broken binary rather than a missing one-line setting. The first two repositories happened to set it already, which is exactly why the third found it.

**A deployment value says what a merge sets off** — Added in Stage 6. `core/git-flow.md` closes by telling a reader that this repository's deployment rules say what the merge triggered, so `deployment/cli/conventions.md` opens with what the tag ships and only then reaches exit codes and streams — one item more than the Stage 6 bullet listed, because that bullet predates the paragraph. A second fragment for the release was the alternative and was rejected: `library/api-stability.md` already folds its versioning rules into a fragment named for something else, and one fragment per deployment value is the shape of the axis. The general form: every deployment value answers "what does a merge do here", or that cross-reference lands on nothing in every repository selecting it.

**Adoption pins, it does not track** — Added in Stage 6. agent-config's `check` gate fetches the binary its own `.agentprofile.yml` pins, exactly as every consumer's does, rather than the one its workspace builds. A fragment edited here therefore reaches this repository's own composed files through a release and a pin bump, not immediately. Running the working tree's binary was the alternative, and it is not adoption: it would couple every fragment pull request to regenerating this repository's configuration and quietly reverse *central first* in the one repository that defines it. The cost is that agent-config is the last repository still reading the old wording after a change ships, which is the right cost for the one that publishes it.

**A publisher that consumes itself ratchets** — Added in Stage 6, found by asking before merging rather than by merging. A repository that publishes agentcfg and pins it puts its release version and its `config_version` on one number line: Renovate's bump pull request merges as `chore(deps): …`, `bump-version.yml` reads that subject and releases from it, and the pin is a patch behind again — one pull request a week, forever, of nothing but rewritten provenance stamps. Observed rather than predicted, in `claude-mit-rust-template`, where pull requests 17 and 18 cut v0.4.1 and v0.4.2; harmless there because the two versions are unrelated number lines. The fix is local, in agent-config's own `renovate.json`, which disables the agentcfg update so the pin moves by hand in the change that warrants it — step 8 of `/new-value`. Not in `bump-version.yml`, where it would stop bump merges cutting releases in seventy-five repositories that want them to.

**The budget is a gate, not an intention** — The always-on set staying small is the assumption the whole composition rests on — it is why the glossary went to a file and why concerns are path-scoped. Stated in a plan and enforced by nobody, it decays: four fragments added over a year degrade every session in every repo with no one noticing. So `check` measures it and fails past a central threshold, and the fix when it trips is moving content behind `scope: paths`, never deleting a rule. What counts is everything loaded unconditionally, which includes the description line of every model-invocable skill — otherwise the cheapest way to evade the gate would be to move rules into a surface it does not measure. What does not count is what never reaches context: `invocation: user` descriptions, and HTML comment lines, which Claude Code strips. Counting either would push authors toward the wrong choice just to pass the gate.

**Reversible on purpose** — `agentcfg eject` strips the markers, leaves the composed files as ordinary checked-in content, and deletes the profile and manifest. It costs almost nothing to build and it answers the only fair objection to centralising 75 repos — "what if this turns out to be wrong in a year". A repo can leave without a rewrite, which is also what makes adopting it a small decision rather than a large one.

**Substitution yes, control flow never** — One pass of `{{ name }}`, and no `{% if %}`, `{% for %}` or inheritance — a deliberate line, and a revision of the earlier "no templating engine at all". Substitution removes a real defect: without it `core/git-flow.md` has to say "run the repo's full gate command" where it could say `just ci`, and vague guidance is worse guidance. Control flow is the opposite — it would let `language/rust/testing.md` ask what the deployment is, which is precisely the cross-axis coupling the single-axis refactor bought and composition already handles additively. Wanting an `{% if %}` is the diagnosis that content belongs in another fragment; an engine without one forces that conclusion instead of papering over it.

**Variables belong to values, never to repos** — A `values.yml` beside the fragments of each axis value declares what it provides — `language/rust/` says `unit: crate`, `gate_command: just ci`. Repos pick values, never write variables, which is why `vars:` was cut from the profile: a repo restating what `language: rust` already determines is a second copy that eventually disagrees. The gain beyond prose is enforcement — `check` resolves every reference, so a new language value that forgets to define the gate command fails loudly rather than emitting quietly vague rules for months.

**Architecture supplements core** — DDD's build-order rule (domain, then application, then infrastructure) is an *addition* to the ordering rule in `core/execution-order.md`, shipped as part of `ddd/layers.md` — core is never edited to accommodate an axis. Composition makes constraints additive, which is the property control flow in the fragments would have cost us — a conditional in `core/` is how this stops being composition and starts being one big template with branches.

**agent-config is public** — Not incidental — it is what makes "no cross-repo credential" true. A consumer's `GITHUB_TOKEN` is scoped to its own repo and cannot fetch a release from a private sibling — and two paths need exactly that: the `check` gate in each repo's CI, and the `just agentcfg` recipe on a laptop. Private would mean handing both a read credential for a sibling repo. The content is commit format, layering rules and when to open a transaction — conventions, not secrets. Anything that ever is a secret stays in a marker region in the private repo that owns it, never in a shared fragment.

**Non-interactive by default** — A tool that prompts cannot run in a workflow, and the workflow is the primary caller. `init` is the single exception and only on a TTY with something genuinely missing. `sync` never prompts even when it is about to lose something — it errors, because prompting on destruction is how people learn to hit `y`. The corollary is that error messages carry the entire user experience, so they get the polish budget a wizard would otherwise have absorbed.

**Auto-merge is per repo, and it lives in .github** — Three presets — `github>ninoverse/.github:agentcfg-automerge-never`, `-patch`, `-minor`, one root-level file each — selected by one line in a repo's `renovate.json`, defaulting to no auto-merge when a repo extends only the base preset, so automation is opted into rather than inherited. Not a field in the profile: Renovate opens the PR, so Renovate decides, and a setting the deciding tool cannot read is decoration. 75 repos reviewing a weekly PR by hand ends in rubber-stamping, which is the failure the release-notes summary exists to prevent, while a repo that wants every change read should be able to say so. Majors need no rule at all — the shared preset already holds every major behind `dependencyDashboardApproval`. Which means the version number has to carry meaning for prose, so it does. **Patch**: wording, examples, clarification — no rule changes meaning. **Minor**: a new fragment, value or rule, additive, nothing you were doing becomes wrong. **Major**: a rule reversed or removed, a fragment renamed, or a profile schema change — something you were doing is now wrong, or your profile needs editing. Releases pick one of the three deliberately; that judgement is a step in `/new-value` and the release checklist.

**MIT, like the templates** — agent-config is public and carries the same licence as `claude-mit-*`. Stated rather than assumed, because a public repo without a LICENSE grants nothing and the fragments are meant to be copyable.

**Axes are observed** — An axis earns its existence by being observed across repos, never anticipated. Deployment qualified because all three current repos already differ on it; sensitivity is declared empty because retrofitting it later is the expensive case. Concurrency, protocol and visibility were rejected as derived, or as plain variables two paragraphs reference. Values are the separate and much cheaper question, governed by *central first*.

**A short ref is not a pin** — Every repository called these workflows at `@v1`, which looked like a pin and behaved like neither thing it resembles. It was a lightweight tag created once by hand and never moved, four commits behind `main`, and no amount of waiting would have changed that: Renovate's `github-actions` versioning prefers the shortest tag that works, so a short ref resolves an upgrade and writes itself back unchanged, moving only when a `v2` appears. `@main` propagates with no pull request; `@v1` produced neither propagation nor pull request. Only a full version does both, which is the propagation the rule "pin the tag, not @main" was written to get. `ninoverse/.github` now cuts SemVer tags on every merge and every caller pins one; `v1` is frozen where it stood, referenced by nothing. The version has to mean something for a workflow too, and the non-obvious half is that a job's `name:` is the status check name every caller's branch protection refers to by string — renaming a job is a major.

**A four-hour window is not a schedule** — The central run fires `0 4 * * 1` and the preset allowed branch creation only `before 6am on monday`. A GitHub cron is a request rather than a promise: scheduled workflows are delayed under load, and the two runs that fired this way started at 09:26 and 09:28 on consecutive Mondays, both outside the window. Renovate evaluates `schedule` when it would create a branch, so those runs extracted dependencies and opened nothing. Proven rather than inferred on 2026-09-21, when work was definitely pending — three templates ten releases behind on `config_version`, every caller a workflow release behind — and the run produced zero pull requests. Renovate's own documentation warns off the shape: *"Avoid schedules like 'Run Renovate for an hour each Sunday' as you will run into problems."* The window is now the whole of Monday, in cron, and `lockFileMaintenance` is a day range rather than a weekday because the trigger only fires Mondays and cron ORs the two day fields when both are restricted. One property is lost and is written down rather than left to be found: a push to `default.json` on a Monday now delivers pull requests org-wide instead of only validating the config.

**Deferred on purpose** — Framework fragments, the Cursor emitter, the plugin marketplace, and `hmi-components`. Each is additive; none is blocked by anything built here. Also the fleet view — which repos are behind on `config_version` — which is a read-only scheduled workflow in agent-config rendering a table into its own README, not a feature of the binary. It is worth nothing at three repos and obvious at thirty.

## What could go wrong

### The spec read moves the emitter design

**Closed at Stage 0.** The AGENTS.md side held: nested-file semantics differ by agent — Codex supplements, Copilot is unspecified, Claude Code reads no AGENTS.md at all — and concern scopes are globs no single nested file can express, so root-level pointers remain the only strategy. What moved was the claude emitter's `surface:` model, revised to `invocation:` before any code depended on it. Detail in `docs/stage-0-spec-read.md`.

### Context budget on the always-on set

Every `scope: always` body and the on-demand index load unconditionally in every session, and adherence degrades well before 200 lines. **Measured at Stage 2**, where `check` began holding the line automatically: 88 lines for `rust`/`tag-only`/`template`, 119 with an architecture, 91 with three concerns — against 200. A test keeps the real profiles under three-quarters of the ceiling, since a profile sitting at 199 is one fragment from tripping. If it does run long, the fix is moving more content behind `scope: paths` — not trimming the rules.

### Stage 4 leans on one Renovate feature

Reading the implementation rather than the issue titles disposes of most of what was flagged here: post-upgrade changes are collected from `git status`, and untracked files, deletions and renames are each handled explicitly, all filtered through `fileFilters` (default `**/*`). New rule files commit, and orphans the manifest removes commit as deletions.

What is left is narrower. Commands run *without a shell* unless `allowShellExecutorForPostUpgradeCommands` is enabled globally, so the task is a sequence of bare invocations rather than a pipeline, each matching `allowedCommands` after Handlebars compilation — and a miss records an artifact error on the PR rather than passing quietly, which is the failure you want. The task also runs only when the manager actually changed a file, so it can never self-heal drift; that is `check`'s job, not its own.

The real exposure is structural: every repo's agent config now depends on a self-hosted-only feature that executes commands inside the run holding the org-wide token. If that surface changes, or ninoverse moves to Mend-hosted Renovate, Stage 4 gets rebuilt — but only Stage 4. The fragments, the binary, the profile and the check gate are untouched, and the fallback is the per-repo sync workflow this replaced.

**Closed at Stage 4, and the reading held.** The commands run as three bare invocations, the allowlist matches them after Handlebars compilation, and `fileFilters` at its default keeps the gitignored binary out of the commit — all confirmed by a real bump pull request rather than by reading the implementation a second time. The structural exposure above is unchanged and remains the accepted cost.

### Neutralised prose reading as vague

Largely solved rather than mitigated, now that `{{ gate_command }}` renders to `just ci` in the repo that reads it — the composed output names things instead of gesturing at them. What survives is the residue: a sentence whose *structure* assumes a language, not just its nouns. "Add the crate to the workspace members list" has no Go reading however the noun is substituted, and no variable catches that. It stays an editorial hazard in Stage 1, just a much smaller one.

Stage 3 could not close it, and that is worth saying plainly: a sentence that assumes Rust reads perfectly well in the Rust template, so the pilot is the wrong instrument. Composing the go profile and reading it turned up no Rust vocabulary and no Rust-shaped structure outside the go language fragments themselves, which write from the Go side ("there is no per-package manifest", "the analog of an MSRV"). That narrows it. The test is Stage 5, which rolls out `claude-mit-go-template` first for exactly this reason.

**Closed at Stage 5, and it held.** The composed Go tree carries no Rust vocabulary and no Rust-shaped sentence: the substitution renders package, module, `make ci` and `golangci-lint` throughout, and the template concern speaks of placeholder packages and an empty module. One sentence was imprecise rather than vague — the claim that the toolchain fails on an empty container, true of a cargo workspace and not of a Go module — which is the residue this entry predicted, at one occurrence in 89 always-on lines.

### Concerns and architecture arguing over the same rule

Both are path-scoped and language-neutral, so a rule can plausibly land in either. The boundary that has to hold: **concerns are hazards of an activity** ("a database is slow, it locks, it N+1s" — true whether or not you do DDD), **architecture is where things may live and what shape they keep**. The pair composes correctly where it matters: data-access says put multiple writes in one transaction, DDD says never write two aggregates at once, and together they say one aggregate, one transaction. Watch for the first rule that genuinely fits both, and write down which axis won and why.

### Concern globs that match nothing

Path-scoped rules silently never fire when globs miss. A repo whose data access lives somewhere unexpected gets no data-access rules and no error. `check` therefore warns when *no* pattern a rule declares matches anything (Stage 2) — per rule, because a concern lists alternatives deliberately and the rule fires if any one of them hits, so warning per pattern put eleven warnings on a healthy repo. It stays a warning: a repo can legitimately declare a concern before the code that triggers it exists, and a failure there would punish exactly the repos doing it right.

## Glossary

Split by provenance, because it tells you which terms you can look up and which only exist here.

### Coined for this project

**axis** — A dimension a repository varies on — language, framework, architecture, deployment, concerns, sensitivity. An axis holds *values*; a profile picks between them, and how many it may pick is that axis's cardinality. Six exist. Adding one is a field in every profile, a dimension in every emitter test, and a question every new repo must answer, which is why an axis has to be observed across several repos before it exists. `core/` is not an axis: it has no values and is always included.

**agentcfg** — The Rust binary. Reads a profile, selects fragments, runs emitters. It never parses markdown — bodies pass through untouched but for one `{{ name }}` substitution pass — so the work is frontmatter splitting, selection, substitution and emission. Seven subcommands: `sync`, `check`, `plan`, `why`, `notes`, `init`, `eject`.

**always-on budget** — The ceiling on what loads in every session, 200 lines to start, declared centrally and enforced by `check`. Measured rather than derived: every non-blank, non-comment line that renders into `AGENTS.md` and `CLAUDE.md`, plus one per model-invocable skill description. Path-scoped and on-demand *bodies* do not count against it — they cost only the sessions that reach them, though the index line or pointer that reaches them does. It is the constraint that keeps composition honest: without it, every fragment added anywhere is a tax on every session everywhere.

**cardinality** — How many values of one axis a single repo may pick. `language` and `deployment` take exactly one, `framework` and `architecture` none or one, `concerns` any number including none. It is a property of the axis, not of a fragment, and the profile schema enforces it.

**central first** — No repo declares a value that agent-config has not released. It replaces an earlier "a value earns its existence at the second repo", which was over-cautious about values and had an exception it could not survive — `language` and `deployment` are mandatory picks, so their values are always earned by the first repo needing them. Enforced by the tool rather than by memory: valid values are the embedded directory listing. Axes remain guarded separately, because an axis costs at every repo and a value costs only at its own.

**drift check** — `agentcfg check` running in a consumer repo's CI. Recomposes the expected output and exits non-zero if a generated file was hand-edited, or if the always-on set is over budget. This is what makes duplicating bytes into every repo safe rather than a fiction.

**eject** — The exit. Strips the markers, leaves the composed files in place as ordinary checked-in content, removes the profile and manifest. The repo stops being managed and loses nothing — deliberately not the same door as `emit: []`, which deletes the composed files and keeps the repo managed. Its purpose is mostly psychological, and none the less real for it: reversibility is what makes adoption a small decision.

**emitter** — Translates selected fragments into one agent's file layout — same bodies, different frontmatter and paths. `agents-md` and `claude` in v1. A new agent is a new emitter, never a content migration.

**fragment** — One markdown file of instructions, the smallest unit — it lives inside exactly one axis value (or inside `core/`). Agent-neutral body; neutral frontmatter carrying `scope` (`always`, `on-demand` or `paths`), `when` on the on-demand ones, `title`, `order` where sequence matters, `emit` where only some agents should read it, and `invocation` on the task-shaped ones. A repo composes 17 of them today; v1 authors 33 in total.

**manifest** — `.agentcfg-manifest.json` — every path the tool generated in this repo. Without it, dropping a concern from a profile leaves an orphaned rule file that nothing ever deletes.

**marker region** — The span between `<!-- agentcfg:start -->` and `<!-- agentcfg:end -->`. Generated content lives inside; anything outside survives regeneration untouched. The escape hatch for genuinely repo-local content, such as the agent template's measured MSRV rationale.

**profile** — `.agentprofile.yml` — the entire per-repo footprint. Names the repo's coordinate on each axis plus the pinned `config_version`, and drives both the fragment selection and the emitted settings.

**provenance comment** — The label each emitted block opens with — source fragment and the `config_version` that produced it. It answers the question centralising creates: a rule you disagree with is no longer a file in your repo you can edit, it is one of twenty-one fragments composed from six axes. The comment makes that traceable in the file itself, makes `why` a lookup, and gives every hunk of the Monday diff a name.

**single-axis refactor** — The Stage 1 editorial pass: rewriting each existing file so it belongs to exactly one axis. It is what removes the crate/package and `just`/`make` vocabulary problem without control flow — the words move into the language value, and the core fragment references them as variables instead of choosing between them.

**values.yml** — The variable declarations of one axis value, sitting beside its fragments. Not a fragment itself — nothing emits it — so it does not count toward the thirty-three. It is the other half of the single-axis refactor: fragments stop naming a language's vocabulary and reference it, and `check` fails when a value omits something a fragment asks for.

**value** — One option on an axis, and one directory in the tree — `rust` and `go` are values of `language`; `service`, `library`, `tag-only` and `cli` are values of `deployment`. A value contains fragments. Picking a value is what pulls its fragments into the composition.

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