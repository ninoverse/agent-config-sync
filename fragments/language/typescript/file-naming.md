---
title: Directories and file naming
scope: on-demand
when: Creating new files
---

## Repository layout

| Path | Contents |
|------|----------|
| `package.json` | Name, version, scripts, dependencies, `engines.node`, and the `packageManager` pin. |
| `pnpm-lock.yaml` | The lockfile. Committed, and changed only by pnpm. |
| `pnpm-workspace.yaml` | pnpm's settings, and the workspace's packages once there are several. |
| `.nvmrc` | The Node version development runs on. |
| `tsconfig.json` | Compiler options, with project references where the build has several parts. |
| `biome.json` | Format and lint configuration. |
| `src/` | Source of the root package. |
| `packages/<name>/` | One directory per package, in a workspace. |
| `dist/` | Build output. Git-ignored. |

## Per-package layout

| Path | Contents |
|------|----------|
| `src/index.ts` | Entry point: the public API, re-exported from the modules that implement it. |
| `src/<module>.ts` | Implementation, one concern per file. |
| `src/<module>.test.ts` | Tests for that file, beside it. |
| `tests/` | Integration tests against the public API. Optional. |

## Naming conventions

| Item | Convention | Example |
|------|------------|---------|
| Package name | lowercase `kebab-case`, scoped when published | `@ninoverse/data-store` |
| Files and directories | `kebab-case` | `user-repository.ts` |
| Test files | the source file's name plus `.test` | `user-repository.test.ts` |
| Classes, interfaces, types, enums | `PascalCase` | `UserRepository`, `RepoError` |
| Functions, methods, variables | `camelCase` | `findById`, `dbPool` |
| Type parameters | short `PascalCase` | `T`, `TKey` |

## Barrel files

An `index.ts` that re-exports a directory is worth having where it is a public
entry point: the package's root, or a subpath listed in `package.json`'s
`exports`. Elsewhere, import the module directly. A barrel inside a package
hides import cycles and makes every importer load everything it re-exports.
