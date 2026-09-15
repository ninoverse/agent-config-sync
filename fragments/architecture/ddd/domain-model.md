---
title: Domain model
scope: paths
paths:
  - "**/domain/**"
---

## Building blocks

- **Entities** have an identity that outlives their attribute values. Compare
  them by identity.
- **Value objects** are immutable and compared by value. Validate in the
  constructor, so an invalid instance cannot exist; never expose a way to build
  one that skips validation.
- **Aggregates** group entities and value objects behind one root. Code outside
  the aggregate holds and calls only the root, and the root enforces every
  invariant the aggregate owns.

## Rules

- Behaviour lives on the model. Prefer `order.cancel(reason)` to setting a status
  field from outside.
- An aggregate is the transaction boundary: one transaction changes one
  aggregate. A use case that must change two coordinates them through the
  application layer or a domain event, never one transaction.
- Refer to another aggregate by its identifier, never by holding the object.
- Domain failures are typed domain errors, not persistence or transport errors.

## Naming goes through the glossary

The ubiquitous language is kept in `docs/domain/glossary.md` (see *Bounded
contexts*). Before introducing or renaming a type, check the glossary; if the
term is new, add it in the same commit. A type's doc comment is its definition —
the glossary entry points to the type rather than restating it.
