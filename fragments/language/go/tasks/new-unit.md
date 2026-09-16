---
name: new-package
title: Adding a package
when: Adding or modifying a package
description: Add a package to the module following the 9-step package workflow
argument-hint: "<package-name> [one-line description of what it does]"
---

The exact procedure for adding or modifying a single package in this Go module.
Follow every step in order; do not skip or reorder.

The package to add: $ARGUMENTS

---

## Pre-flight

Before writing any code:

1. **Ask for confirmation.** State which package you are about to add and what it
   will contain. Wait for explicit approval. Do not start on your own initiative.

2. **Check if the package already exists:**
   ```bash
   ls internal/<pkg>/ 2>/dev/null && echo EXISTS || echo MISSING
   ```
   If it exists, report the finding and ask: skip / overwrite / modify.
   Never silently overwrite.

Decide the location before scaffolding: `internal/<pkg>/` for a private package,
`cmd/<binary>/main.go` for an executable, `pkg/<pkg>/` only if it is genuinely
meant for import from outside this module.

---

## 9-step checklist (one package, one commit)

Complete all nine steps before committing. Never commit a partial package.

### 1. Scaffold the package

```bash
mkdir -p internal/<pkg>          # use cmd/<binary> for an executable instead
```

Package directory and name are short and all-lowercase (e.g. `internal/store`,
`package store`). A binary lives at `cmd/<binary>/main.go` with `package main`.

### 2. First file

Create `internal/<pkg>/<pkg>.go` (or `cmd/<binary>/main.go`) with the matching
`package` clause. There is no per-package manifest — Go discovers the package
from its directory.

### 3. Public API surface

- Export only what callers need; keep the rest unexported (lowercase).
- Every exported identifier gets a doc comment starting with its own name
  (`// New returns …`).
- The package gets a `// Package <pkg> …` comment, in `doc.go` or atop the
  primary file.

### 4. File split

Any file growing past ~150 LOC, or holding a distinct concern, moves to its own
lowercase `.go` file in the same package (e.g. `repository.go`, `errors.go`).

### 5. Unit tests

`<file>_test.go` beside the code, using table-driven subtests:

```go
func TestDoThing(t *testing.T) {
    cases := []struct {
        name string
        in   int
        want int
    }{
        {"doubles", 2, 4},
    }
    for _, tc := range cases {
        t.Run(tc.name, func(t *testing.T) {
            if got := DoThing(tc.in); got != tc.want {
                t.Errorf("DoThing(%d) = %d, want %d", tc.in, got, tc.want)
            }
        })
    }
}
```

### 6. Examples + black-box tests

- `Example` functions with an `// Output:` comment document and verify usage;
  they run under `go test` and appear in `go doc`.
- For consumer-facing coverage, use `package <pkg>_test` files that import the
  package as an outside caller would.

### 7. Dependencies & wiring

Cross-package use is a plain import:
`import "<module-path>/internal/<other>"`, with the module path from `go.mod`.
New third-party dependencies are added with `go get <module>` and land in
`go.mod`/`go.sum` — run `go mod tidy` before committing.

### 8. Verification gate

```bash
make ci
```

Every gate, zero findings, before committing. See *Testing instructions* for
what it runs.

Two that catch people out on a *new* package specifically:

- `revive` requires a package comment as well as a doc comment on every exported
  identifier, so a package is red until it has one.
- `goimports` groups this module's own imports last. An import block `gofmt`
  accepts can still fail `make fmt-check`.

### 9. Commit + push, then hand the PR over

```
feat(<pkg>): add <pkg> package
```

One package per commit, one commit per branch. Never batch multiple packages.

Push the branch, output the PR title and description, and **stop** — the user
opens and merges it. Wait for the merge before starting the next package. The
full loop, and why it is not a stack, is in *Git flow*.

---

## Before committing

Points that are easy to get wrong, so verify each one:

- A **package comment** (`// Package <pkg> …`) on one file, and a doc comment
  starting with the identifier's own name on every exported identifier. `revive`
  enforces both, so the package is red without them.
- Imports of this module are grouped last by `goimports`. An import block that
  `gofmt` accepts can still fail `make fmt-check`.
- Every returned `error` is checked in non-test code — `errcheck` is on, and
  `_ =` does not satisfy it. Errors are wrapped with `%w` as they propagate.
- At least one test, table-driven with subtests where there are multiple cases.
- `make ci` passes before you commit.
