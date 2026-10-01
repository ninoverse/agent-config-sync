---
title: Testing instructions
scope: on-demand
when: Testing/Verifying
---

## Before merging any change

```bash
pnpm run ci
```

That runs every gate in order, stopping at the first failure:

- [ ] `pnpm lint` — Biome's format and lint check, warnings as errors
- [ ] `pnpm typecheck` — the type check, `tsc`
- [ ] `pnpm test` — the test suite
- [ ] `pnpm build` — the build

All must pass before pushing the branch. The underlying tool commands live in the
`package.json` scripts; call the script rather than copying them. A repository
with checks of its own adds them to `ci`, after these four.

## What CI adds

The CI workflow calls the organization's reusable `node-ci.yml`, which runs the
same four scripts as separate jobs, so a red build names the gate that broke.
Running `pnpm run ci` locally first is still the rule — CI is the backstop, not
the first place you find out.

Two things CI checks that a local run does not:

- **The Node floor.** A job installs on the exact `engines.node` floor with
  `engine-strict` on, so a dependency that needs a newer Node fails by name.
  For a library, the package is packed and installed into an empty project on
  the floor, and its entry points are imported, as a consumer would. Locally you
  run the `.nvmrc` Node, so you would never notice.
- **Advisories over time.** `pnpm audit` runs weekly, because a new advisory
  lands against dependencies you already have, with no commit to trigger a push
  build.

## Test layout

| Test type | Location | When to use |
|-----------|----------|-------------|
| Unit | `<file>.test.ts` beside the file under test | The default: one test file per source file |
| Integration | `tests/<feature>.test.ts` | Exercising the package's public API as a consumer would |
| Type | `<file>.test-d.ts`, with Vitest's `expectTypeOf` | Exported types whose shape is part of the API. Optional. |
| Fixtures | files under a `fixtures/` directory beside the tests | Static inputs |

## Running specific tests

```bash
pnpm test <file>              # one file
pnpm test -t '<test name>'    # tests whose name matches
pnpm --filter <package> test  # one package of a workspace
```

## Watching tests during development

```bash
pnpm exec vitest              # re-runs the affected tests on save
```
