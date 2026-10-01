---
name: new-package
title: Adding a package
when: Adding or modifying a package
description: Add a package to the workspace following the 9-step package workflow
argument-hint: "<package-name> [one-line description of what it does]"
---

The exact procedure for adding or modifying a single package in this pnpm
workspace. Follow every step in order; do not skip or reorder.

The package to add: $ARGUMENTS

---

## Pre-flight

Before writing any code:

1. **Ask for confirmation.** State which package you are about to add and what it
   will contain. Wait for explicit approval. Do not start on your own initiative.

2. **Check if the package already exists:**
   ```bash
   ls packages/<name>/package.json 2>/dev/null && echo EXISTS || echo MISSING
   ```
   If it exists, report the finding and ask: skip / overwrite / modify.
   Never silently overwrite.

A repository whose only package is at its root becomes a workspace with this
one. Say so when you ask: the root keeps its own package, and gains the
`packages:` list.

---

## 9-step checklist (one package, one commit)

Complete all nine steps before committing. Never commit a partial package.

### 1. Scaffold the package

```bash
mkdir -p packages/<name>/src
```

The directory is `kebab-case` (e.g. `packages/data-store`), and so is the
package name, scoped like the root's when there is a scope.

### 2. `packages/<name>/package.json`

- `name`, and `"private": true` unless the package is published.
- `"type": "module"`, and `exports` naming its entry point.
- The contract scripts this package needs — `lint`, `typecheck`, `test`,
  `build` — so `pnpm --filter <name> <script>` works.
- Dependencies the root already has take the root's ranges.

### 3. `packages/<name>/tsconfig.json`

Extend the root's compiler options rather than restating them. If the root
type-checks with `tsc -b`, give this file `"composite": true` and add it to the
root `tsconfig.json`'s `references`, or the type check never sees the package.

### 4. `packages/<name>/src/index.ts`

- Public API surface only. Implementation lives in modules beside it.
- Every export gets a TSDoc comment (`/** … */`).

### 5. Module split

Any file growing past ~150 LOC, or holding a distinct concern, moves to its own
`kebab-case.ts` module in `src/`.

### 6. Tests

`<module>.test.ts` beside the module it tests, run by the package's `test`
script. At least one before committing.

### 7. Workspace wiring

`pnpm-workspace.yaml` lists `packages/*`; add the `packages:` key if this is the
first. Another workspace package that depends on this one names it as
`"<name>": "workspace:*"`. Then `pnpm install`, which links the package and
updates `pnpm-lock.yaml`.

### 8. Verification gate

If `.agents/new-package.local.md` exists, follow it now, before the gate. It
holds the steps this repository adds to this checklist; it is written by hand,
and `agentcfg` leaves it alone.

Every gate must pass, with zero warnings, before committing:

```bash
pnpm run ci
```

### 9. Commit + push, then hand the PR over

```
feat(<name>): add <name> package
```

One package per commit, one commit per branch. Never batch multiple packages.

Push the branch, output the PR title and description, and **stop** — the user
opens and merges it. Wait for the merge before starting the next package. The
full loop is in *Git flow*.

---

## Before committing

Points that are easy to get wrong, so verify each one:

- The package's `package.json` has the contract scripts it needs, and
  `"private": true` unless it is published.
- If the root type-checks with `tsc -b`, its `tsconfig.json` references the
  package, and the package's own has `"composite": true`.
- Every export from `src/index.ts` has a TSDoc comment.
- At least one test, beside the module it tests.
- `pnpm-lock.yaml` was updated by `pnpm install` and is committed with the
  package.
- `pnpm run ci` passes before you commit.
