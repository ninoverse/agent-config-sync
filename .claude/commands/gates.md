---
description: Run the four merge gates and report exactly which pass or fail
argument-hint: "[optional: -p <crate> to scope to one crate]"
allowed-tools: Bash(just:*), Bash(cargo:*)
---

Run the four merge gates defined in `.claude/testing-requirements.md`:

```
just ci
```

If `just` is not installed, fall back to the four commands individually
(`cargo fmt --all -- --check`, `cargo lint`, `cargo test --workspace`,
`cargo deny check`) and say that `just` is missing.

Extra arguments, if any: $ARGUMENTS

Then report a one-line-per-gate summary:

- Which of the four gates passed and which failed.
- For each failure, the specific file and line, and the actual error — not a
  paraphrase.
- Whether any gate could not run because its tool is not installed. Do not
  report a skipped gate as a passing gate.

Do not fix anything unless asked. This command reports; it does not edit.
