---
title: Testing instructions
scope: on-demand
when: Testing/Verifying
---

## Before merging any change

```bash
make ci
```

That runs every gate in order:

- [ ] `make fmt-check` — `golangci-lint fmt --diff`, no formatting drift
- [ ] `make vet` — `go vet ./...`
- [ ] `make lint` — golangci-lint, zero findings
- [ ] `make test-race` — gotestsum with `-race` and coverage *(falls back to `go test` if gotestsum is not installed)*
- [ ] `make vuln` — govulncheck
- [ ] `make licenses` — go-licenses

All must pass before pushing the branch. The underlying go commands live in the
`Makefile`; call the target rather than copying them — that is also the one place
the `golangci-lint` version is pinned.

## What CI adds

`.github/workflows/ci.yml` calls the organization's reusable `go-ci.yml`, which
runs the same targets as separate jobs so a red build names the gate that broke.
Running `make ci` locally first is still the rule — CI is the backstop, not the
first place you find out.

Three things CI checks that a local run does not:

- **No silent toolchain upgrade.** One job builds with `GOTOOLCHAIN=local`.
  Locally you have `GOTOOLCHAIN=auto`, so a dependency requiring a newer Go makes
  your toolchain quietly download it and succeed — the declared floor becomes a
  lie and nothing says so.
- **That the declared floor is still true.** That job takes its version from the
  `go-version` input in `ci.yml` rather than from `go.mod`, so the two drifting
  apart fails there instead of going unnoticed.
- **Advisories over time.** `.github/workflows/audit.yml` runs weekly, because a
  new advisory lands against dependencies you already have, with no commit to
  trigger a push build.

Coverage is produced as a downloadable HTML artifact on every run. It is not a
gate — nothing fails on a coverage number.

## Test layout

| Test type | Location | When to use |
|-----------|----------|-------------|
| Unit | `<file>_test.go` beside the code, `package <pkg>` (white-box) | Testing internal logic with access to unexported identifiers |
| Black-box | `<file>_test.go`, `package <pkg>_test` | Exercising only the package's exported API, as a consumer would |
| Example | `func Example...()` with a trailing `// Output:` comment | Documented usage that compiles, runs under `go test`, and shows in `go doc` |
| Table-driven | subtests via `t.Run(name, ...)` over a slice of cases | The default shape for unit tests with multiple input/output cases |
| Benchmark | `func Benchmark...(b *testing.B)` in a `_test.go` file | Performance tracking. Optional. |
| Fixtures | files under a `testdata/` directory | Static inputs; the `testdata` name is ignored by the Go toolchain |

## Running specific test types

```bash
go test ./internal/<pkg>/...                  # one package
go test -run TestName ./internal/<pkg>/       # one test
go test -run Example ./...                     # examples only
go test -bench . ./internal/<pkg>/            # benchmarks
go test -race -coverprofile=coverage.txt ./...  # race + coverage
```

## Watching tests during development

```bash
gotestsum --watch -- ./...
```
