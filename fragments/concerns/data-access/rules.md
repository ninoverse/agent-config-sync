---
title: Data access
scope: paths
paths:
  - "**/migrations/**"
  - "**/*.sql"
  - "**/repository/**"
  - "**/repositories/**"
  - "**/store/**"
  - "**/db/**"
---

## Transactions

- Writes that must succeed or fail together go in one transaction.
- Keep transactions short. No network calls, user input or unbounded loops while
  one is open.

## Queries

- No query inside a loop over results (N+1). Load the set in one query, with a
  join or an `IN` list.
- Select the columns you use, and bound every list query with a limit.

## Migrations

- Forward-only. Never edit a migration that has been applied anywhere; add a new
  one.
- A destructive change takes two releases: first make the new shape available
  and stop using the old one, then remove the old one. Code and schema from
  adjacent releases must work together, because they run together during a
  deploy.

## Locks

- Take locks in one consistent order across the codebase, so two transactions
  cannot deadlock on each other.
- Lock the rows you will change and nothing more, and never hold a lock while
  waiting on anything outside the database.
