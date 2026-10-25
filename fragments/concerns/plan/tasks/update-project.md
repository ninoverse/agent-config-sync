---
name: update-project
title: Updating a project
when: Running a project in phases
description: Record what changed in a project run in phases, and publish its page
argument-hint: "<page> [what changed]"
---

Changes a project's data as *Project phases* says, and publishes its page again.

The project, and what changed: $ARGUMENTS

## Steps

1. Read the data as last published into a directory of its own: the copy kept
   at the last publish or, for a page published as a claude.ai artifact, each
   `src/<file>` beside it, read by path with the Artifact tool. Edit a copy of
   it, since `--since` compares with the data as read.
2. Read the notes for the next session, under `[handoff]`, then the Brief.
3. Make the change in the data, never on the page:
   - a status takes `on`, the day, and its `result`, `why` or `waits`;
   - an item that no longer belongs is `dropped`, with `why`, never deleted;
   - an item added to the Brief, the Research, the Analysis or the Plan once
     it is done, or approved, or edited there, is `amended`, with the day and
     why;
   - new work in Execution or Verify, once done, reopens it, with `reopened`;
   - a decision, or a question, is written in full, with its options and the
     one recommended, before the user is asked to take it: they read it on
     the page, and the chat only says it is there;
   - a decision taken has its `chosen` option, and `on`;
   - a phase that starts with a draft, the Research, the Analysis, the Plan,
     Reuse or the Retrospective, is `draft`, its `draft` in its own file, a
     list of paragraphs and lists of points, and the chat only says it is
     there; once the user accepts it, the phase is `now`, with `accepted`, the
     day, and the Plan keeps its draft, as its summary, while another phase
     drops it;
   - an item set aside is `deferred`, with what it waits on, or `to-move`,
     naming the project that takes it.

   Show: each change, in the words the page will use.
4. After a merge, also:
   1. confirm the merge from the PR, and check what it released, as *Git flow*
      says;
   2. mark the PR `done`, `on` its merge day, with its `result`: what it
      released, and what its *Done when* showed;
   3. start the next PR in that repository, the one the board has Ready there,
      with the user's go where the ground rules ask for it.

   Show: the merge, and what it released.
5. Update the notes for the next session, under `[handoff]`: what is in flight,
   where, and what comes next.
6. Publish with `/publish-project`, which reads the state again, renders with
   `--since` and tells the user what changed.
