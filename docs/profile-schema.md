# Profile Schema

`.agentprofile.yml` is the entire per-repo footprint of this system, and the
only file in a consumer repository a human writes. Everything else is
generated, and `agentcfg check` fails when a generated file has been
hand-edited.

`sync` only ever *reads* this file. That is a correctness constraint rather
than a preference: Renovate's custom manager owns `config_version` during a
bump, and a post-upgrade task that rewrote the file would have the manager's
version silently discarded.

> Where this file and `docs/plan.md` disagree, the plan is canonical.

## The file

```yaml
config_version: v1.0.0               # required
language:       rust                 # required — exactly 1
framework:      ~                    # optional — 0 or 1
architecture:   ddd                  # optional — 0 or 1
deployment:     service              # required — exactly 1
concerns:       [template]           # optional — any number
sensitivity:    none                 # optional — exactly 1, defaults to none
emit:           [agents-md, claude]  # required — may be empty
settings_extra:                      # optional
  env:
    RUST_LOG: debug
```

## Fields

| Field | Required | Cardinality | Default | Value comes from |
|-------|----------|-------------|---------|------------------|
| `config_version` | yes | one | — | The release tag whose fragments compose this repo |
| `language` | yes | exactly 1 | — | `fragments/language/` |
| `framework` | no | 0 or 1 | none | `fragments/framework/` |
| `architecture` | no | 0 or 1 | none | `fragments/architecture/` |
| `deployment` | yes | exactly 1 | — | `fragments/deployment/` |
| `concerns` | no | any number | `[]` | `fragments/concerns/` |
| `sensitivity` | no | exactly 1 | `none` | `fragments/sensitivity/` |
| `emit` | yes | any number | **none — no implicit default** | The emitters this release ships |
| `settings_extra` | no | one mapping | absent | Written by the repo, not by an axis |

An axis with a cardinality of 0-or-1 is written `~` or omitted entirely; both
mean the same thing. An unknown key is an error rather than something ignored,
so `langauge: rust` fails loudly instead of quietly composing nothing.

## Cardinality is a property of the axis

`language` and `deployment` take exactly one because every repository is
written in a language and every merge does something — or deliberately
nothing, which is what `tag-only` says. `framework` and `architecture` take
none or one. `concerns` takes any number, because concerns are hazards and
stack harmlessly: more caution is never incoherent. Architecture is the
deliberate asymmetry — architectures are prescriptions and can contradict, so
cardinality 1 makes the conflict impossible rather than something review has
to catch.

## Valid values are the directory listing

No repository declares a value that a release has shipped. The legal set for
an axis is the value directories inside it, embedded at build time, so
`language: fsharp` becomes legal the moment `language/fsharp/` ships in a
release, and is a hard error before that. There is no hand-written list to
keep in step.

Two axes ship without content today. `framework` has no directory at all, so
naming any framework is an error until one exists. `sensitivity` ships a
single empty value, `none`, so the axis can be declared now and filled in
later — retrofitting it across dozens of repositories is the expensive case,
and one line today avoids it.

## `emit` has no implicit default

The profile states which emitters it wants; there is no fallback list. So
omitting the key is an error, while writing `emit: []` is a decision — the
manifest then deletes everything previously generated, which is the soft
off-switch. It is distinct from `eject`: one leaves the repo with nothing, the
other leaves it with the composed files as ordinary content.

Because an empty list is reachable by typo, an unknown emitter name is a hard
error. `emit: [agent-md]` fails rather than quietly wiping `.claude/`.

## `settings_extra`

A mapping merged last into the generated `.claude/settings.json`. The claude
emitter owns that file whole and verifies it byte-for-byte, because JSON has
no comment syntax and so cannot carry a marker region — a merging emitter
could never tell a key it wrote last month from one a person added. Repo-local
additions therefore live here, in the profile, rather than in the generated
file.

Not to be confused with `.claude/settings.local.json`, which is the personal
gitignored override and no home for committed repository config.

## What is not in the profile

**Variables.** A `values.yml` beside the fragments of each axis value declares
what that value provides — `language/rust/` says `unit: crate`. Repositories
pick values, never write variables: a repo restating what `language: rust`
already determines is a second copy that eventually disagrees.

**Auto-merge.** Renovate opens the bump PR, so Renovate decides. The setting
is one line in the repo's `renovate.json`, selecting one of the three presets
in `ninoverse/.github`. A setting the deciding tool cannot read is decoration.

## What fails, and what the error says

| Cause | Message |
|-------|---------|
| Missing `language`, `deployment`, `config_version` or `emit` | `missing field ...` |
| An unknown key | `unknown field ...` |
| `config_version` that is not a release tag | ``expected `v<major>.<minor>.<patch>` `` |
| An axis naming a value this release does not ship | `unknown language ... — this release ships: go, rust` |
| An axis that ships nothing yet | `unknown framework ... — this release ships no values for that axis yet` |
| The same concern listed twice | ``listed twice under `concerns:` `` |
| An unknown emitter name | `unknown emitter ... — expected one of: agents-md, claude` |
| `settings_extra` that is not a mapping | `invalid type ...` |

Every message names `.agentprofile.yml`, because the tool never prompts and so
its failures carry the whole user experience.
