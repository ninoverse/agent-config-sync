---
title: Releases and CLI conventions
scope: on-demand
when: Any change that ends in a PR
---

A merged PR ships a binary. `bump-version.yml` tags every push to `main` whose
subject is a conventional commit, and `release.yml` builds one binary per target
from that tag and attaches them to its GitHub release with a `SHA256SUMS`.

The binary is the product, so its surface is a promise: a flag name, an exit
code and the shape of stdout are all things a caller depends on.

## What counts as breaking

Renaming or removing a flag or a subcommand, changing what an exit code means,
and changing the shape of anything written to stdout. Commit it with `!` after
the type — `feat!:` — which cuts a major release. Adding a flag or a subcommand
is a `feat` and a minor one.

## Exit codes

- `0` means the command did what it was asked, and nothing partial or advisory
  ever exits `0`.
- Give a distinct code to each outcome a caller has to branch on, say what it
  means in `--help`, and leave `1` for everything else.
- A failure a user can cause is an error message and an exit, never a panic. A
  backtrace is a bug report, not a diagnostic.

## Streams

- Results go to stdout and nothing else does. Progress, warnings and errors go
  to stderr, so the command composes in a pipe.
- Stdout is something a caller parses: if its shape is not stable, it does not
  belong there.
- Colour and progress only when the stream is a terminal.

## `--help`

- Every command and subcommand carries a one-line description of what it does,
  and every flag one of what it takes.
- The help text is the documentation most callers will read, so keep it current
  in the same commit that changes the behaviour.

## Prompting

- Prompt only when stdin is a terminal. A command that stops to ask inside a
  script or a CI job has hung.
- A flag always wins over a prompt, so a caller that passes every value never
  sees a question.
- `--non-interactive` turns a prompt for a missing required value into a hard
  failure naming the flag that supplies it. A prompt for something optional is
  simply skipped.
