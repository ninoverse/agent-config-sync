---
title: Build and test commands
scope: always
order: -1
---

**Toolchain:** TypeScript on Node, with pnpm only — never `npm` or `yarn`, whose lockfiles and resolution differ. pnpm is pinned by `packageManager` in `package.json`, and Node by `.nvmrc`. Once per machine, install the Node `.nvmrc` names and run `corepack enable`, which then provides the pnpm `packageManager` names.

Commands live in the `package.json` scripts, which are the single source of
truth — do not copy the underlying tool invocations into docs or CI, call the
script.

```bash
pnpm install    # install from the lockfile
pnpm run ci     # every merge gate, in order — run this before every commit
pnpm lint       # gate 1 — format and lint, warnings as errors
pnpm typecheck  # gate 2 — tsc
pnpm test       # gate 3 — the test suite
pnpm build      # gate 4 — the build
pnpm format     # format in place
```

`ci` is called as `pnpm run ci`: `pnpm ci`, like `pnpm audit` and `pnpm docs`,
is pnpm's own command and never reaches the script. Biome and Vitest are the
defaults behind `lint`, `format` and `test`, with `lint` as
`biome check --error-on-warnings .` so a warning fails the gate. A repository
that needs another tool changes the script; the script names stay.

## Architecture & Workspace Rules

**Layout:** One package at the repository root, with its own `package.json`, `tsconfig.json` and `src/`. Once there are several, a pnpm workspace: `pnpm-workspace.yaml` lists `packages/*`, each package lives in `packages/<name>/`, and the root holds the shared tooling.

**Dependencies:** Added with `pnpm add`, recorded in the committed `pnpm-lock.yaml`, and installed in CI with `--frozen-lockfile`. What the shipped code imports goes in `dependencies`; tools only the build and tests use go in `devDependencies`.

**Node floor:** `engines.node` is the oldest Node the package supports, repeated as the `node-floor` input of the workflow that calls `node-ci.yml`, whose floor job fails a partial bump. Raising it means editing both together. Do not raise it incidentally. `.nvmrc` only pins development, and moves freely.
