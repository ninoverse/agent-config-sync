---
name: new-value
title: Adding an axis value
when: Extending the fragment tree
description: Add a value to an axis of the fragment tree following the 8-step value workflow
argument-hint: "<axis> <name> [which repository is waiting for it]"
---

The exact procedure for adding one value to one axis of the fragment tree.
Follow every step in order; do not skip or reorder.

The axis and value to add: $ARGUMENTS

---

## Pre-flight

Before writing any markdown:

1. **Ask for confirmation.** State which axis you are adding to, what the value
   is called, and which repository is waiting for it. Wait for explicit
   approval. A value nothing selects yet is a fragment tree that grows faster
   than anything reads it.

2. **Check the axis, then the value:**
   ```bash
   ls fragments/<axis>/ 2>/dev/null || echo "NO SUCH AXIS"
   ls fragments/<axis>/<name>/ 2>/dev/null && echo EXISTS || echo MISSING
   ```
   An axis with no directory has no legal values at all, so adding one is a new
   axis rather than a new value — a schema change, and not this checklist. If
   the value already exists, report the finding and ask: skip / extend / rename.
   Never silently overwrite.

---

## 8-step checklist (one value, one commit)

Steps 1 to 6 all happen before the commit. Never commit a partial value.

### 1. Create the directory

```bash
mkdir fragments/<axis>/<name>
```

Lowercase, `kebab-case`, and the directory name is what a profile writes
verbatim: `fragments/language/fsharp/` is what makes `language: fsharp` legal.
Valid values are the directory listing, so there is no enum to update and no
code to change — and no repository can name the value until a release ships it.

### 2. Write the fragments its siblings carry

```bash
ls fragments/<axis>/*/
```

Every value of an axis answers the same questions, so the new one carries the
same fragments as the values beside it. A value that ships fewer composes a
repository with a silent gap where the others have a rule. Where a sibling's
fragment genuinely has no counterpart, say so in the PR description rather than
shipping the silence unexplained.

Frontmatter, body conventions and the scope choice are in
`docs/fragment-authoring.md`. The two that are easiest to get wrong: the body
carries no title heading, because the emitter writes `title` as the `#` heading
and sections start at `##`; and another fragment is referenced by its title in
italics — *Git flow* — never by a file path, because where a fragment lands
differs per emitter and its title does not.

### 3. `values.yml`

On the `language` axis this is required, and skipping it fails loudly. Core
fragments substitute names that only a language value supplies, every language
value must define **every** name the others define, and an unresolved name is a
hard error at compose time rather than a blank. The full table is in
`docs/fragment-authoring.md`; copy a sibling's file and replace the values, so a
name cannot go missing.

On any other axis, add one only if a fragment of that value needs it, and pick
names no other value declares — two selected values declaring one name is an
ambiguity the tool refuses rather than resolves.

### 4. Document the value

- For a language, add its column to the vocabulary table in
  `docs/fragment-authoring.md`. The next person authoring a core fragment reads
  that table to learn what they may reference.
- Update whatever else in `docs/` enumerates the axis's values, so the count and
  the directory listing do not drift apart.

### 5. Golden fixture

A fixture pins the shape of a composition — which files, how each is owned, and
the fragments composed into each in order — and is what makes a value's arrival
visible in review. Add one beside the existing fixtures, under
`crates/agentcfg/tests/fixtures/<fixture>/`:

```bash
mkdir crates/agentcfg/tests/fixtures/<fixture>
```

Write `profile.yml` naming the new value, add a test calling
`assert_fixture("<fixture>")` beside the others, then generate the expected
shape:

```bash
AGENTCFG_BLESS=1 cargo test
```

Then **read the generated `expected.txt`**. Blessing is what writes the file;
reading it is what reviews it. A value whose fragments land on the wrong paths
blesses just as cleanly as one that is right.

### 6. Verification gate

Run {{ gates }}, with {{ gates_clean }}, before committing:

```bash
{{ gate_command }}
```

Then compose a repository that selects the value and check it:

```bash
cargo run -p agentcfg -- check --repo <path> --fragments ./fragments
```

An `always` fragment spends the 200-line budget of every repository that selects
the value, and `check` is what reports the cost. If it is over, the fragment to
move behind `scope: on-demand` is the first one the failure lists.

### 7. Commit + push + hand over the PR

```
feat(fragments): add <axis>/<name>
```

`feat` is what makes the release minor, which is what a new value is: additive,
and no existing profile changes meaning. One value per commit, one commit per
branch.

- Push the branch: `git push -u origin feat/<axis>-<name>`.
- Output the PR title and description (*PR instructions*). Do not open the PR —
  the user does that.
- **Stop.** Wait for the merge.

The full loop is in *Git flow*.

### 8. Release, then the consumer's pin

The merge tags a release, and only then can a repository name the value: a
profile pinned to a release whose fragments do not contain the value fails to
compose, so the order is not negotiable.

In the consumer, set `config_version` to the new tag and name the value in its
profile **in one change**, then run `agentcfg sync` and commit the regenerated
files with it. Renovate will offer the pin bump on its own; taking that offer
first is fine, but the profile edit still waits for the tag.

---

## Before committing

Points that are easy to get wrong, so verify each one:

- The new directory carries the same fragments as its siblings, or the PR
  description says which one it omits and why.
- For a language value, `values.yml` defines every name its siblings define.
  A missing one is a hard error in every repository that selects it, not a
  blank.
- No fragment body opens with a title heading, and no fragment references
  another by file path.
- The fixture's `expected.txt` was read, not just blessed.
- `check` is green on a repository that selects the value, budget included.
- `{{ gate_command }}` passes before you commit.
