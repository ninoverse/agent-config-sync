---
title: Architecture layers
scope: always
---

The code is domain-driven, in three layers. Dependencies point inward only:

| Layer | Holds | Depends on |
|-------|-------|------------|
| **domain** | Entities, value objects, aggregates, repository *interfaces*, domain errors | Nothing outside itself but the standard library and small value-type libraries (identifiers, decimals, time) |
| **application** | Use cases: load an aggregate, call its behaviour, save it | domain |
| **infrastructure** | Repository implementations, HTTP handlers, database and external clients, wiring | application, domain |

- The domain imports no framework, persistence, transport or serialisation
  library. When domain code seems to need one, define an interface in the domain
  and implement it in infrastructure.
- Neither domain nor application imports infrastructure.
- A change that spans layers is built in that order: the domain {{ unit }} first,
  then application, then infrastructure, each compiling against what is already
  on `main`. This adds to *Execution order*; it does not replace it.
