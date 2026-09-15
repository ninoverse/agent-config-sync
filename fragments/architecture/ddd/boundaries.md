---
title: Bounded contexts
scope: always
---

- A repository is one bounded context. Its model means what it means here and
  nowhere else; the same word in another service is a different concept.
- Every external boundary — another context's API, a third-party service, a
  shared database — sits behind an anti-corruption layer in infrastructure that
  translates the outside model into this context's types. Foreign types never
  reach the domain.
- The ubiquitous language lives in `docs/domain/glossary.md`, a plain document a
  domain expert can read and correct. It holds the terms that are not types, and
  the synonyms this context deliberately rejects. Types define themselves in
  their doc comments; the glossary points to them.
- The glossary is never shared across contexts. A single glossary for several
  services is how one `Customer` ends up meaning three things.
