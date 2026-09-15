---
title: Repositories
scope: paths
paths:
  - "**/repository/**"
  - "**/infrastructure/**"
---

- One repository per aggregate root. Its interface lives in the domain; its
  implementation lives in infrastructure.
- A repository accepts and returns whole aggregates — never rows, DTOs or a
  partly loaded aggregate.
- No persistence type crosses back into the domain. Row structs, ORM models and
  driver errors are mapped to domain types and domain errors inside the
  implementation.
- No method changes a single field. Changes go through the aggregate's
  behaviour, then the repository saves the aggregate, so invariants cannot be
  bypassed from storage.
- The application layer owns the transaction: it loads, calls behaviour and
  saves within one unit of work, for one aggregate.
