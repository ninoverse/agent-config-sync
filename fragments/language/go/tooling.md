---
title: Build and test commands
scope: always
order: -1
---

**Toolchain:** The Go version is pinned via the `go` and `toolchain` directives in `go.mod` (mirrored in `.go-version`). With `GOTOOLCHAIN=auto` (the default) every contributor automatically downloads the pinned toolchain on first `go` invocation. The full-parity dev tools are `golangci-lint` (lint + format), `gotestsum` (test runner), `govulncheck` (CVE scan), `go-licenses` (license check), and `air` (live reload).

Commands live in the `Makefile`, which is the single source of truth — do not
copy the underlying go invocations into docs or CI, call the target.

```bash
make            # list every target
make ci         # every merge gate, in order — run this before every commit
make build      # build all packages
make fmt        # format in place
make fmt-check  # gate 1
make vet        # gate 2, first half
make lint       # gate 2 — golangci-lint
make test-race  # gate 3 — race detector plus coverage
make vuln       # gate 4 — govulncheck
make licenses   # gate 4 — go-licenses
make cover      # coverage summary
make watch      # dev loop, live reload
```

Install the auxiliary tools once per machine:

```bash
make tools      # golangci-lint, gotestsum, govulncheck, go-licenses, air
```

`make tools-lint`, `tools-test`, `tools-vuln` and `tools-licenses` install one at
a time; that is how CI does it, so each gate pulls only the binary it uses.

## Architecture & Module Rules

**Layout:** A single Go module rooted at the repo. The module path is declared in `go.mod`; dependency versions are centralized in that one file. Code follows the standard Go layout:

- `cmd/<binary>/main.go` — one directory per executable (`package main`).
- `internal/<pkg>/` — private packages, importable only within this module.
- `pkg/<pkg>/` — public packages intended for external import (omit if there are none).

**Packages:** One package per directory; the directory name matches the `package` clause. A new package is just a new directory with a `package` declaration — there is no per-package manifest. Cross-package use is a plain `import "<module-path>/internal/<pkg>"`, with the module path from `go.mod`. New dependencies are added with `go get` and land in `go.mod`/`go.sum`.

**Go version:** The minimum language version is the `go` directive in `go.mod` (the analog of an MSRV). Do not lower it incidentally. There are no editions, no LTO/codegen profiles, and `gofmt` is non-configurable by design.
