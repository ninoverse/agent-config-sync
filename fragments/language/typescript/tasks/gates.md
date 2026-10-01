---
name: gates
title: Merge gates
when: Checking your work
description: Run the merge gates and report exactly which pass or fail
argument-hint: "[optional: --filter <package> to scope to one package]"
allowed-tools: Bash(pnpm run:*), Bash(pnpm lint:*), Bash(pnpm typecheck:*), Bash(pnpm test:*), Bash(pnpm build:*), Bash(pnpm install --frozen-lockfile)
---

Run the merge gates defined in *Testing instructions*:

```
pnpm run ci
```

If `node_modules` is missing, run `pnpm install --frozen-lockfile` first and say
so. If pnpm itself is missing, say that rather than installing it:
`corepack enable` provides the version `packageManager` names.

Extra arguments, if any: $ARGUMENTS

Then report a one-line-per-gate summary:

- Which gates passed and which failed.
- For each failure, the specific file and line, and the actual error — not a
  paraphrase.
- Whether any gate could not run because its tool is not installed. Do not
  report a skipped gate as a passing gate.

`pnpm run ci` stops at the first failing script, so a gate listed after the
failure has not run. Report those as not run, not as passing.

Do not fix anything unless asked. This command reports; it does not edit.
