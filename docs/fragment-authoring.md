# Fragment Authoring Guide

A fragment is one markdown file of agent instructions that belongs to exactly
one axis value, or to `core/`. `agentcfg` selects fragments by a repo's profile,
substitutes `{{ name }}` references, and hands the result to the emitters. It
never parses the markdown, so everything it needs is in the frontmatter.

This file is the reference for writing one. The *procedure* for adding a value
to an axis is `/new-value`, which carries the release and pin steps this one
does not. The profile the fragments compose against is specified in
`docs/profile-schema.md`. `docs/plan.md` holds the design and the reasoning
behind it, and is canonical where it and this file disagree about intent.

## Layout

```text
fragments/
├── core/<name>.md                  always selected — no axis, no cardinality
└── <axis>/<value>/
    ├── values.yml                  the vocabulary this value declares
    ├── settings.partial.json       the Claude settings it contributes
    ├── <name>.md                   a rules fragment
    └── tasks/<name>.md             a task fragment — a skill for Claude
```

`values.yml` and `settings.partial.json` are files rather than fragments: they
carry no frontmatter, nothing emits them on their own, and only `language` values
ship them today.

## What a value contains

Whatever its siblings contain. That parity is the rule, because a value shipping
fewer fragments than the values beside it composes a repository with a silent gap
where the others have a rule. `language` is the fullest axis, and a new language
value is this list:

| File | Scope | Role |
|------|-------|------|
| `tooling.md` | `always` | *Build and test commands* — the command table and the layout rules. `order: -1`, so it leads. |
| `automation.md` | `always`, `emit: [claude]` | What the settings hooks already do, so Claude does not redo it by hand. |
| `code-review.md` | `on-demand` | This language's own review rules — error handling, unsafe code, public API docs. Read alongside core's *Code review*. |
| `testing.md` | `on-demand` | *Testing instructions* — what the gates run, and what CI adds on top of them. |
| `file-naming.md` | `on-demand` | Directory layout and file naming. |
| `tasks/gates.md` | — | `/gates`: runs the gates and reports which passed. |
| `tasks/new-unit.md` | — | `/new-crate`, `/new-package`: the checklist for adding one unit. Its `name:` substitutes. |
| `values.yml` | — | The twelve names listed under `values.yml` below. |
| `settings.partial.json` | — | The permission allowlist and hooks for this language, merged by the claude emitter into `.claude/settings.json`. |

Seven fragments, then, and two files that are not. A `deployment` or `concerns`
value is far smaller — one or two fragments and usually no `values.yml` — because
it answers a narrower question.

## Frontmatter

Every fragment except a task fragment:

| Field | Required | Meaning |
|-------|----------|---------|
| `title` | yes | The heading the emitter writes above the body. Use an AGENTS.md section name where the fragment genuinely is one: *Build and test commands*, *Testing instructions*, *Code style guidelines*, *Security considerations*, *Commit message guidelines*, *PR instructions*. |
| `scope` | yes | `always`, `on-demand` or `paths` — see *Choosing a scope*. |
| `when` | with `on-demand` | The activity that triggers reading it, written as the lead-in of its index line: `Committing code` renders as "**Committing code:** read …". Fragments that share a `when` share one index line. |
| `paths` | with `paths` | List of globs, in Claude Code `paths:` syntax. |
| `order` | no | Integer, default `0`, lower first. Ties break by axis (core, language, framework, architecture, deployment, concerns, sensitivity), then by path. Set it only where position helps a reader. |
| `emit` | no | The emitters that receive this fragment, e.g. `[claude]`. Default: every emitter the profile selects. Use it only for content that is false for the other agents. The claude emitter writes an `always` claude-only fragment below `CLAUDE.md`'s `@AGENTS.md` import, and it counts only against Claude's budget. |

A task fragment, under `tasks/`, becomes a skill for Claude and a pointer in
AGENTS.md. It keeps `title` and `when`, which label that pointer, takes no
`scope` or `paths`, and adds:

| Field | Required | Meaning |
|-------|----------|---------|
| `name` | yes | The skill name, typed as `/name`. May use substitution: `name: "new-{{ unit }}"`. |
| `description` | yes | The condition the model tests to decide whether to load it. Counts against the budget unless `invocation: user`. |
| `invocation` | no | `model` (default) or `user`. A `user` skill's description never enters context. |
| `argument-hint`, `arguments`, `allowed-tools` | no | Passed to the claude emitter unchanged; the agents-md emitter drops all three, so a body must never depend on them — see *Body* on `$ARGUMENTS`. |

## Body

- No title heading. The emitter writes `title` as the `#` heading, so sections
  start at `##`.
- Refer to another fragment by its title in italics — *Git flow* — never by file
  path. Where a fragment lands differs per emitter; its title does not. Inside a
  code block, drop the italics: `# see Branch naming`.
- Keep the body agent-neutral. Claude-only mechanics — hooks, settings, skill
  fields — live in `settings.partial.json`, task frontmatter, or a fragment with
  `emit: [claude]`.
- In a task body, take arguments through `$ARGUMENTS` and nothing else, on a
  line that reads as a label a reader can skip: "The crate to add: $ARGUMENTS".
  Claude binds it; every other agent prints it. A named `arguments:` entry or a
  `$name` binds for Claude too and stays literal text in `.agents/` — which is
  how one came to sit a few lines above `cargo new --lib crates/<name>` in a
  document that is mostly bash, where an agent resolving it the shell way writes
  `crates/$name`. Placeholders inside commands are `<name>`, never a `$`.

## Substitution

- `{{ name }}` is replaced anywhere in the file, frontmatter included, by `name`
  from the `values.yml` of a selected value.
- An unresolved name is a hard error, never an empty string.
- `\{{` writes a literal `{{`.
- A frontmatter string containing `{{` must be quoted, or YAML reads it as a
  mapping.
- Substitution only — no conditionals, loops or includes. Wanting one means the
  content belongs in another fragment.

## values.yml

A flat map of names to strings, beside the fragments of one axis value. Every
value of an axis defines the same names, and `check` fails when a fragment
references a name the selected values do not define. Values are substituted
verbatim, so they may carry markdown.

Core references these, so every `language` value defines all of them:

| Name | rust | go |
|------|------|----|
| `unit` | `crate` | `package` |
| `units` | `crates` | `packages` |
| `unit_container` | `workspace` | `module` |
| `gate_command` | `just ci` | `make ci` |
| `gates` | `all four gates` | `every gate` |
| `gates_clean` | `zero warnings` | `zero findings` |
| `unit_lint_command` | `cargo clippy -p <crate> --all-targets -- -D warnings` | `golangci-lint run ./internal/<pkg>/...` |
| `unit_test_command` | `cargo nextest run -p <crate>` | `gotestsum -- -race ./internal/<pkg>/...` |
| `version_floor` | `MSRV` | `Go version` |
| `lint_suppression` | ``` `#[allow(...)]` attribute ``` | ``` `//nolint:...` directive ``` |
| `dependency_bump_example` | `tokio to 1.40` | `golang.org/x/sync to v0.10.0` |
| `breaking_change_example` | `bump MSRV to 1.85` | `drop support for Go 1.24` |

## Choosing a scope

- **`always`** loads every session in every repo that selects it, and every line
  counts against the always-on budget below. Reserve it for what an agent needs
  before it knows what it is doing: how to behave, how to build and test.
- **`on-demand`** loads when the agent reaches the activity named in `when`. Only
  its index line counts. Most rules belong here — git flow, commits, reviews. It
  is the pattern the source repos already used, as a hand-written list of
  pointers in `CLAUDE.md`.
- **`paths`** loads when the agent reads a file matching the globs, and nothing
  counts. For rules about a kind of code rather than a kind of activity. It does
  not fire when the agent *creates* the first matching file, only when it reads
  one.

## The always-on budget

200 lines, declared centrally and enforced by `check` rather than remembered. It
is the assumption the whole composition rests on: `always` content loads in every
session of every repository that selects it, so one fragment added here is a tax
on all of them at once, and four added over a year degrade every session with
nobody noticing.

What counts is everything that loads unconditionally — every non-blank,
non-comment line the generated regions of `AGENTS.md` and `CLAUDE.md` actually
render, plus one line per model-invocable skill description, since a description
the model tests is loaded whether or not the skill runs. What does not count is
what never reaches a session: an `invocation: user` description, and HTML comment
lines, which Claude Code strips before loading.

`check` prints the figure on every run, so the cost of a fragment is one command
away:

```
Up to date. Always-on set: 78 of 200 lines.
```

When it trips, the fix is moving content behind `scope: on-demand` or
`scope: paths`. Never delete a rule to fit, and never trim one until it is vague
— a rule nobody can act on costs the budget and buys nothing. The failure lists
the always-on fragments largest first, so the one to move is the first line you
read.

## Single-axis discipline

Every fragment belongs to exactly one axis value, and what decides which is not
what the fragment is about but **what would have to change for it to stop being
true**. If the answer is a noun or a command, it is core, and the noun becomes a
variable. If the answer is the shape of the sentence — "add the crate to the
workspace members list" has no Go reading however the nouns are substituted — it
belongs to the language value. One source file often splits across both.

Judgement calls made so far, so the next extraction makes the same ones:

- **Command strings are vocabulary.** A command a core rule names goes in
  `values.yml` (`unit_test_command`) rather than becoming "run the tests".
- **Examples take a variable only at the language-specific point.** The commit
  examples keep neutral scopes (`store`, `httpclient` — valid as a crate and as a
  Go package) and substitute only the dependency and breaking-change examples.
- **A variable cannot start a sentence or a table cell**, since values are
  lowercase. Reword: "Group of {{ units }}", not "{{ unit }} group".
- **Split by content, not by file.** One source file can feed two axes:
  `code-review.md` gives core its gate, dependency and test checks, and gives
  each language its idioms.
