---
name: resume-project
title: Resuming a project
when: Running a project in phases
description: Pick a project run in phases back up in a new session, from its page
argument-hint: "<page>"
---

Starts a session on a project another session ran, from what its page holds.

The project: $ARGUMENTS

## Steps

1. Read the data as last published into a directory of its own: for a page
   published as a claude.ai artifact, each `src/<file>` beside it, read by path
   with the Artifact tool; otherwise the copy kept at the last publish. Edit a
   copy.
2. Read the notes for the next session, under `[handoff]`, then the Brief,
   before anything else: its ground rules hold until the user changes them.
3. Read each PR in flight again, from GitHub, set `read_at`, and render with
   `--since`, given the data as published: what changed is what happened while
   no session ran. Fix what stops the render.
4. Tell the user where the project stands: the phase in progress and who holds
   the ball, as the render prints them, and what is in flight and what comes
   next, as the notes say; then what changed since the last publish. Show: that
   summary, and each warning.
5. Carry on with what the notes say comes next, asking the user first about
   anything they leave open.
