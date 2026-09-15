---
title: Synchronisation
scope: paths
paths:
  - "**/sync/**"
  - "**/queue/**"
  - "**/worker/**"
  - "**/consumer/**"
  - "**/webhook*/**"
---

## At-least-once delivery

- Assume every message, webhook and retry arrives more than once. A handler that
  is not safe to run twice is a bug.
- Acknowledge a message only after its effects are committed.

## Idempotency keys

- Every operation that changes state carries an idempotency key chosen by the
  sender.
- The receiver records processed keys alongside the change, in the same
  transaction, and answers a repeated key with the original result instead of
  acting again.

## Ordering

- Do not assume messages arrive in order unless the transport guarantees it for
  that key, and say which guarantee you rely on.
- Carry a version or sequence number, and reject an update older than the state
  it would replace.

## Conflicts

- Decide how each kind of record resolves concurrent changes — version check,
  last-writer-wins on a server-assigned version, or a merge — and write that
  decision next to the code.
- Never resolve a conflict by silently overwriting. A rejected write is reported
  or recorded.
