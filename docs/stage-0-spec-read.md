# Stage 0 — What the spec actually says

Read 2026-09-15 against primary sources (listed at the end), replacing the
secondary sources the plan was designed on. **Verdict: the emitter design holds
on AGENTS.md; the claude emitter's `surface:` model moves.** Four things change,
listed under *What moves*.

## 1. Frontmatter collision — none

AGENTS.md has no frontmatter convention and no required fields:

> "No. AGENTS.md is just standard Markdown. Use any headings you like; the agent
> simply parses the text you provide." — agents.md FAQ

Nothing collides with `scope:` / `paths:`. The corollary is that the agents-md
emitter must strip fragment frontmatter completely: a YAML block in AGENTS.md is
not ignored, it is read as prose.

## 2. Nested files — "closest wins", but agents disagree on what that means

The spec itself only says:

> "The closest AGENTS.md to the edited file wins; explicit user chat prompts
> override everything." — agents.md FAQ

It does not say whether the parent is still read. Implementations split:

| Agent | Behaviour | Source wording |
| --- | --- | --- |
| Codex | **Supplement** — concatenated root → cwd, later overrides earlier on conflict | "Codex concatenates files from the root down … Files closer to your current directory override earlier guidance because they appear later in the combined prompt." |
| Copilot | **Unspecified** | "the nearest `AGENTS.md` file in the directory tree will take precedence." |
| Claude Code | **Not read at all** | "Claude Code reads `CLAUDE.md`, not `AGENTS.md`." A root `@AGENTS.md` import never sees nested files. |

**Decision: root-level pointers stay the only strategy for concerns.** Nested
emission is unsafe under replace semantics (a subdirectory loses every core
rule), invisible to Claude, and structurally wrong regardless: concern scopes
are globs like `**/domain/**` spanning many directories, not one directory a
file can sit in. The "second viable emission strategy" in *What could go wrong*
does not materialise.

## 3. Section headings worth matching

The spec's suggested sections: **Project overview · Build and test commands ·
Code style guidelines · Testing instructions · Security considerations**, plus
"commit message guidelines, PR standards … deployment steps". Its own example
uses *Dev environment tips*, *Testing instructions*, *PR instructions*.

No code change — a Stage 1 editorial convention. Fragment `title:` values should
land on these headings where a fragment genuinely is one of them
(`tooling.md` → *Build and test commands*, `testing.md` → *Testing
instructions*, `sensitivity/*` → *Security considerations*), so the composed file
reads as AGENTS.md rather than as a concatenated `.claude/`.

## 4. Skills — all three answers are "yes", and commands are gone

From the Claude Code skills docs:

- **Slash-invocable:** yes, by default. `disable-model-invocation: true` makes it
  user-only; `user-invocable: false` makes it model-only.
- **Arguments:** yes — `$ARGUMENTS`, `$ARGUMENTS[N]`, `$N`, and named `$name` via
  an `arguments:` list, with `argument-hint:` for autocomplete. Shell-style
  quoting. If no placeholder consumes them, `ARGUMENTS: <input>` is appended.
- **`allowed-tools`:** native to skills, not an equivalent. Pre-approves the listed
  tools for the invoking turn only; restricts nothing.

And the fact the plan did not have:

> "Custom commands have been merged into skills. A file at
> `.claude/commands/deploy.md` and a skill at `.claude/skills/deploy/SKILL.md`
> both create `/deploy` and work the same way." — on a name clash, the skill wins.

Context cost by invocation flag:

| Frontmatter | Description in context every session? |
| --- | --- |
| (default) | yes |
| `disable-model-invocation: true` | **no** |
| `user-invocable: false` | yes |

## What moves

1. **`surface: skill | command | both` → `invocation: model | user`** (default
   `model`). Both values emit `.claude/skills/<name>/SKILL.md`; `user` adds
   `disable-model-invocation: true`. The claude emitter stops writing
   `.claude/commands/`. `both` has no correct rendering — the command file is
   shadowed by the skill of the same name — and `command` is now just a skill
   flag. The locked decision's substance survives unchanged: invocation is still
   declared per fragment, and still decides who pulls the trigger.
2. **The budget counts descriptions of model-invocable skills only.** A
   `user` skill's description never enters context, so counting it would push
   authors toward the wrong surface to pass the gate.
3. **`$1` in the existing commands is the second argument.** `new-crate.md` and
   `new-package.md` in all three repos write "Add a new crate named `$1`"; per
   the current docs `$0` is the first argument and a missing index stays literal,
   so `/new-crate foo` asks for a crate named `$1`. Joins the Stage 1 drift
   reconciliation; `tasks/new-unit.md` should use a named `arguments:` list.
   Confirm by invoking `/new-crate` once in a template repo before fixing.
4. **HTML comments are free for Claude, not for anyone else.** "Block-level HTML
   comments in CLAUDE.md files are stripped before the content is injected into
   Claude's context." Codex reads them as text. The always-on budget should count
   neither markers nor provenance comments — one per fragment is 18 of the 200
   lines, spent on the reader that does not need them. Whether stripping also
   applies to the `@AGENTS.md` import is not stated; it does not change the rule.

## Confirmed unchanged

- **AGENTS.md canonical, CLAUDE.md as `@AGENTS.md` adapter** — this is exactly
  the pattern the Claude Code docs recommend, including Claude-specific content
  below the import.
- **Path-scoped rules** in `.claude/rules/` with `paths:` globs, rules without
  `paths:` always loaded, target under 200 lines per file.
- **Pointers for AGENTS.md** — no agent offers glob scoping in AGENTS.md itself.

## Noted, no design change

- **Path-scoped rules fire on read, not write.** "Path-scoped rules trigger when
  Claude reads files matching the pattern." A brand-new `domain/` whose first file
  Claude creates gets no DDD rules until something matching is read. Strengthens
  the empty-glob warning; worth a line in *What could go wrong*.
- **Codex caps the combined AGENTS.md chain at 32 KiB** (`project_doc_max_bytes`)
  and silently stops adding files past it. 200 lines is far below that, so the
  line budget covers it.
- **Skills also accept `paths:`** — a task fragment could be path-scoped later.
  Not needed in v1.
- Per-skill description + `when_to_use` truncates at 1,536 characters.

## Sources

- agents.md site and FAQ — <https://agents.md>,
  `components/FAQSection.tsx` and `components/HowToUseSection.tsx` in
  <https://github.com/agentsmd/agents.md>
- Codex — <https://learn.chatgpt.com/docs/agent-configuration/agents-md>
- Copilot — <https://docs.github.com/en/copilot/how-tos/configure-custom-instructions/add-repository-instructions>
- Claude Code skills — <https://code.claude.com/docs/en/skills>
- Claude Code memory and rules — <https://code.claude.com/docs/en/memory>
