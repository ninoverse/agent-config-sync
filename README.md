# agent-config

One source of truth for the coding-agent instructions used across the ninoverse
repositories. Rules are written once here as small single-purpose fragments,
composed per repository according to that repository's profile, and delivered as
ordinary committed files — `AGENTS.md` first, everything else adapted from it.

Read by any agent that reads `AGENTS.md`, which is most of them: Codex, Copilot,
Cursor, Gemini CLI, Jules, Zed, Aider and others. Claude Code gets a generated
`CLAUDE.md` and `.claude/` tree alongside.

> **Status: nothing is built yet.** This repository is at Stage 0 of
> [`docs/plan.md`](docs/plan.md), which carries the seven-stage build sequence and
> the reasoning behind every decision. The README below describes the design in the
> present tense because that is how a README stays useful; the plan is what says
> when each part arrives.

## Why this exists

Three template repositories had accumulated ten to twelve near-identical `.claude/`
files each. Nine of ten were byte-identical between the two Rust templates. That
is tolerable at three repositories and untenable at seventy-five, which is where
this is going: four or five languages, a few frameworks each, and several
orthogonal concerns.

Copying does not scale, and neither does a repository per combination — five
languages times three frameworks times four deployment shapes is sixty template
repositories nobody maintains. Composition does.

## How it works

Three levels, and keeping them straight is the whole model:

- An **axis** is a dimension a repository varies on — `language`, `framework`,
  `architecture`, `deployment`, `concerns`, `sensitivity`.
- A **value** is one option on an axis, and one directory in the tree — `rust` and
  `go` are values of `language`.
- A **fragment** is a single markdown file of instructions inside a value. It
  belongs to exactly one axis, and nothing else.

```
fragments/
├── core/                 always included — nothing to pick
├── language/             pick exactly 1     rust/  go/
├── framework/            pick 0 or 1        (none yet)
├── architecture/         pick 0 or 1        ddd/
├── deployment/           pick exactly 1     service/  library/  template/  cli/
├── concerns/             pick any number    data-access/  sync/
└── sensitivity/          pick exactly 1     none/  (declared, no content yet)
```

A repository names its coordinates in one file:

```yaml
# .agentprofile.yml
config_version: v1.0.0
language:     rust
architecture: ddd
deployment:   service
concerns:     []
sensitivity:  none
emit:         [agents-md, claude]
```

`agentcfg` selects the fragments inside those values, substitutes the vocabulary
each value declares, and writes the result. That profile composes 18 fragments.
Drop the `architecture` line and it composes 14.

Updates arrive through the central Renovate run in `ninoverse/.github`: it bumps
`config_version`, regenerates the files in the same commit, and opens one pull
request. `agentcfg check` runs in each consumer repository's CI, so a generated
file that was hand-edited fails the build rather than drifting quietly.

## If you arrived here from a provenance comment

Every generated block is labelled with the fragment that produced it. From a
consumer repository:

| You want to | Do this |
| --- | --- |
| Find which fragment states a rule | `just agentcfg why "<phrase>"` |
| Change a rule for everyone | Open a pull request here, against the fragment |
| Change it for one repository only | Put it in that repo's marker region — generated content is only what sits between `<!-- agentcfg:start -->` and `<!-- agentcfg:end -->` |
| See what an update would change | `agentcfg plan` |
| Change how updates merge | One line in that repo's `renovate.json`, picking `:agentcfg-automerge-never`, `-patch` or `-minor` |
| Stop being managed | `agentcfg eject` — strips the markers, keeps the files as ordinary content, removes the profile |

There is no global install. Each repository carries a `just agentcfg` recipe that
fetches the version pinned in its own profile, so a laptop cannot run a different
version than CI.

## Adding a language, concern or architecture

`/new-value <axis> <name>` walks the checklist. The rule it enforces is
**central first**: no repository declares a value this repository has not
released. Adding F# means writing `fragments/language/fsharp/`, cutting a release,
and only then bumping the consuming repository's pin — two pull requests in two
repositories, in that order.

You do not have to remember this. Valid values are the embedded directory listing,
so `language: fsharp` is a hard error until that directory ships.

Adding an **axis** is a different matter and deliberately harder: an axis is a
field in every profile and a question every new repository must answer. Values are
cheap; axes are observed across several repositories before they exist.

## Versioning

The version number carries meaning for prose, because auto-merge depends on it:

- **patch** — wording, examples, clarification. No rule changes meaning.
- **minor** — a new fragment, value or rule. Additive; nothing you were doing
  becomes wrong.
- **major** — a rule reversed or removed, a fragment renamed, or a profile schema
  change. Something you were doing is now wrong, or your profile needs editing.
  Never auto-merged anywhere.

Choosing between the three is a step in the release checklist, not an afterthought.

## Invariants

Break these and the design stops working. They are argued out in `docs/plan.md`;
this is the short list.

1. **A fragment belongs to exactly one axis.** No fragment asks what another axis
   is set to.
2. **Substitution yes, control flow never.** `{{ name }}` only — no conditionals,
   no loops, no inheritance. Wanting an `{% if %}` means the content belongs in a
   different fragment.
3. **Variables belong to values, never to repositories.** A repository picks
   values; it does not restate what they imply.
4. **`sync` never writes `.agentprofile.yml`.** Renovate's manager owns that file
   during an update, and a post-upgrade task that rewrites it has its version
   silently discarded.
5. **The always-on set stays under budget.** `check` enforces it. When it trips,
   move content behind `scope: paths` — never delete a rule.
6. **Core is never edited to accommodate an axis.** Axes supplement core
   additively. If core needs a branch, the design has gone wrong.
7. **Every generated file is entirely generated.** Local content lives in a marker
   region, or in the profile for formats without comments.

## Layout

```
fragments/                  the rules — one directory per axis, one per value inside it
crates/agentcfg/            the composer: lib + bin, no markdown parser
docs/plan.md                build sequence, decisions, glossary
docs/fragment-authoring.md  how to write a fragment
docs/profile-schema.md      the .agentprofile.yml schema
```

## Commands

```
agentcfg sync     compose and write
agentcfg check    exit 1 on drift or budget overrun
agentcfg plan     what would change, and why
agentcfg why      which fragment states this
agentcfg notes    what a release adds, changes and removes
agentcfg init     scaffold a profile
agentcfg eject    stop being managed, keep the files
```

Everything but `init` is non-interactive by design. `init` prompts only on a
TTY: for a required value it was not given, and for the one thing composition
cannot supply — a sentence on what this repository is, which it writes above the
composed region in `AGENTS.md`.

## What this is not

Not a scaffolder. It does not create projects, run `git init`, or write
`Cargo.toml` — those are one-time acts, and this tool manages a relationship that
lasts. The seam between the two is `.agentprofile.yml`: anything that creates a
repository can write one, and `agentcfg` takes over from there.

## Licence

MIT. Same as the templates it came from.