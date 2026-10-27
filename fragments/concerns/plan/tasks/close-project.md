---
name: close-project
title: Closing a project
when: Running a project in phases
description: Close a project run in phases once its objective is met
argument-hint: "<page>"
---

Closes a project once the user says its objective is met, leaving its page as
the record of it, and Deferred as the list of what waits.

The project: $ARGUMENTS

## Steps

1. Agree with the user that the objective is met, against the Brief's success
   criteria: each Met, or dropped with why. Show: each criterion and where it
   stands.
2. Settle every unfinished item: `done`; `dropped`, with `why`; `deferred`,
   with what it waits on; or `to-move`, naming the project that takes it. An
   item set aside no longer holds its phase open.
3. End each phase on its real day: Execution with its last item done, Verify
   with its last check, and Reuse and the Retrospective the day the project
   closes, never before the phases they run beside. Deferred stays Now while it
   lists what waits.
4. Write the Retrospective's lessons with the user, unless they say it isn't
   needed, which the page then says, with why. An adopted lesson's change waits
   in Deferred until it ships. Its story is only for a project shown outside it.
5. Set the project's `[state]` to `closed`, `on` the day it closes, and update
   the notes for the next session: the project is complete, where its work
   went, and what still waits.
6. Publish with `/publish-project`. The page now opens on Deferred, or on the
   Retrospective when nothing waits.
