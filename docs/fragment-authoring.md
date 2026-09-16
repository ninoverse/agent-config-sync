# Fragment Authoring Guide

> **Draft.** Started in Stage 1 while the fragments are extracted; Stage 6 edits
> it into shape. Where this file and `docs/plan.md` disagree, the plan is
> canonical and this file is wrong.

A fragment is one markdown file of agent instructions that belongs to exactly
one axis value, or to `core/`. `agentcfg` selects fragments by a repo's profile,
substitutes `{{ name }}` references, and hands the result to the emitters. It
never parses the markdown, so everything it needs is in the frontmatter.

## Layout

```text
fragments/
├── core/<name>.md
└── <axis>/<value>/
    ├── values.yml
    ├── <name>.md
    └── tasks/<name>.md
```

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
| `argument-hint`, `arguments`, `allowed-tools` | no | Passed to the claude emitter unchanged; the agents-md emitter drops them. Name arguments with `arguments` rather than indexing `$0` / `$1`. |

## Body

- No title heading. The emitter writes `title` as the `#` heading, so sections
  start at `##`.
- Refer to another fragment by its title in italics — *Git flow* — never by file
  path. Where a fragment lands differs per emitter; its title does not. Inside a
  code block, drop the italics: `# see Branch naming`.
- Keep the body agent-neutral. Claude-only mechanics — hooks, settings, skill
  fields — live in `settings.partial.json`, task frontmatter, or a fragment with
  `emit: [claude]`.
- In a task body, Claude replaces `$name` and `$ARGUMENTS`; every other agent
  reads them literally. Write so the sentence works either way — "The crate:
  `$name`." — and keep `<name>` placeholders in commands, where a literal `$name`
  would be pasted into a shell.

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
  counts against the always-on budget (200 lines). Reserve it for what an agent
  needs before it knows what it is doing: how to behave, how to build and test.
- **`on-demand`** loads when the agent reaches the activity named in `when`. Only
  its index line counts. Most rules belong here — git flow, commits, reviews. It
  is the pattern the source repos already used, as a hand-written list of
  pointers in `CLAUDE.md`.
- **`paths`** loads when the agent reads a file matching the globs, and nothing
  counts. For rules about a kind of code rather than a kind of activity. It does
  not fire when the agent *creates* the first matching file, only when it reads
  one.

## Single-axis discipline

Judgement calls made so far, so the next extraction makes the same ones:

- **Neutralise the noun, not the sentence.** If only a word is language-specific,
  it becomes a variable. If the sentence's structure assumes a language, it is
  not core.
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
