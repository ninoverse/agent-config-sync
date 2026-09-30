---
title: Releases and API stability
scope: on-demand
when: Any change that ends in a PR
---

A merged PR is a release, not a publish. `bump-version.yml` tags every push to
`main` whose subject cuts a release, and `release.yml` turns the tag into a
GitHub release carrying the packaged library, its checksum and a changelog. No
registry serves that version until someone publishes it.

Other code depends on this repository's public API, so its version number is a
promise about that API.

## After the merge

- Check the release, not the run: the version it took, the package attached to
  it, and the range its changelog covers.
- A version number is used once. npm and crates.io refuse to publish over one,
  and consumers' lockfiles record its checksum, so a wrong release is corrected
  by the next version, never by moving its tag.

## Publishing

- `publish-<registry>.yml` runs by hand with a release's tag and publishes that
  release's package, so the registry serves byte for byte what the release
  holds.
- Publish a release only if its version matches its changes. A breaking change
  released as a minor reaches every consumer whose range accepts it.
- If the repository deploys a docs site, it deploys with the publish, not with
  the tag, so it documents the version its readers can install.

## What counts as breaking

Removing or renaming a public item, changing a public signature or error type,
accepting less input or returning less output than before, and raising the
toolchain floor the package declares to its consumers. When unsure, treat it as
breaking.

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

## Dependencies

- A dependency's range is a range every consumer inherits. Raise its minimum
  only when the code needs the newer version, in the change that needs it; a
  routine update moves the lockfile alone.

## Documentation

- Every public item has a doc comment, and every public function a runnable
  example unless its behaviour is obvious from the signature.
- Do not expose a dependency's types in the public API unless that is
  deliberate: a major release of the dependency becomes a breaking change of
  this one.
