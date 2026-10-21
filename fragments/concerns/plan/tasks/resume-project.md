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
   published as a claude.ai artifact, list its files with the Artifact tool,
   and read each `src/<file>` by path, which saves it under `src/`; otherwise,
   the copy kept at the last publish. Edit a copy of it, since `--since`
   compares with the data as read.
2. Read the notes for the next session, under `[handoff]` in `project.toml`,
   then the Brief, `brief.toml`, before the other phases: its ground rules hold
   until the user changes them.
3. Read the state again, from GitHub: each PR item with a `url` that isn't
   `done` or `dropped`, and, for one without a `url`, whether a PR has opened
   from its `Branch`. A PR merged is `done`, `on` its merge day, with its
   `result`; one closed without a merge is the user's call, `dropped` or
   replaced; one still open is `open` once it waits only on the user, else
   `ready` or `blocked`; one with no PR yet keeps its status. Set `read_at`
   to now, in UTC, and render with `--since`, given the data as published:

   ```bash
   python3 .agents/create-project/render.py <data directory> <out directory> \
     --since <published directory>
   ```

   What it lists is what happened while no session ran. Fix every problem,
   and fix each warning or tell the user why it stands. Show: each PR read,
   and its state.
4. Tell the user where the project stands: the phases in progress and who
   holds the ball, as the render prints them, and what is in flight and what
   comes next, as the notes say; then what changed since the last publish.
   Show: that summary, and each warning.
5. Carry on with what the notes say comes next, asking the user first about
   anything they leave open.
