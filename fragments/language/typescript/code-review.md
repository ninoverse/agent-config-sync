---
title: TypeScript code review
scope: on-demand
when: Reviewing PRs
---

Read alongside *Code review*, which holds the checks every language shares.

## What to check

### Types
- No `any`. Take `unknown` and narrow it — `typeof`, `instanceof`, a type
  guard — before using the value. Where `any` is genuinely unavoidable, such as
  an untyped third-party API, keep it to one place with a comment saying why.
- No `as` cast or non-null assertion (`!`) standing in for a check the code
  could make. A cast is a claim the compiler cannot verify.
- `@ts-expect-error` rather than `@ts-ignore`: it fails once the error it hides
  is gone, so a stale suppression cannot outlive its reason.

### Errors and promises
- No floating promises. Every promise is awaited, returned, or handed off with
  `void` and a comment saying why — otherwise its rejection vanishes.
- `catch (error)` treats `error` as `unknown` and narrows it before reading
  `.message`.
- Only `Error` instances are thrown, never strings or plain objects, so every
  failure carries a stack.

### Public API
- Every exported function, class, type and constant has a TSDoc comment
  (`/** … */`), with `@param` and `@returns` where the signature does not say
  it all.
- No `console.log` left in code that ships.

### Dependencies
- `pnpm audit` is clean, or the advisory is accepted in `pnpm-workspace.yaml`
  with the reason beside it.
- What the shipped code imports is in `dependencies`, not `devDependencies`.
- A change that does raise the `engines.node` floor edits it and the
  `node-floor` input of the workflow that calls `node-ci.yml` together — see
  *Build and test commands*.

### Tests
- New behavior is covered by a test, and `pnpm test` runs it.
