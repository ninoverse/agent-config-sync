---
name: resume-project
title: Resuming a project
when: Running a project in phases
description: Pick a project run in phases back up in a new session, from its page
emit: [claude]
argument-hint: "<artifact url>"
---

Starts a session on a project another session ran, from what its page holds.

The project: $ARGUMENTS

## Steps

1. Read the page with the Artifact tool, then each `src/<file>` beside it by
   path, into a directory of its own: the data as last published. Edit a copy.
2. Read the notes for the next session, under `[handoff]`, then the Brief,
   before anything else: its ground rules hold until the user changes them.
3. Read the state again, as the first step of `/publish-project` says, and
   render with `--since`, given the data as published: what changed is what
   happened while no session ran. Fix what stops the render.
4. Tell the user where the project stands: the phase in progress, who holds
   the ball, what is in flight and what comes next, as the notes and the page
   say; then what changed since the last publish. Show: that summary, and each
   warning.
5. Carry on with what the notes say comes next, asking the user first about
   anything they leave open.
