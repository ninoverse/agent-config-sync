---
title: Public API stability
scope: on-demand
when: Changing the public API
---

Other code depends on this repository's public API, so its version number is a
promise about that API.

## What counts as breaking

Removing or renaming a public item, changing a public signature or error type,
accepting less input or returning less output than before, and raising the
minimum supported toolchain. When unsure, treat it as breaking.

## Versioning

- The version is never edited by hand. `bump-version.yml` derives it from the
  merged commit: `feat` is a minor release, `fix` and the other maintenance types
  a patch.
- A breaking change is committed with `!` after the type — `feat!:` — or a
  `BREAKING CHANGE` footer, which cuts a major release.

## Deprecation

- Deprecate before removing: mark the item deprecated in a minor release, name
  its replacement in the deprecation message, and remove it only in the next
  major release.

## Documentation

- Every public item has a doc comment, and every public function a runnable
  example unless its behaviour is obvious from the signature.
- Do not expose a dependency's types in the public API unless that is
  deliberate: a major release of the dependency becomes a breaking change of
  this one.
