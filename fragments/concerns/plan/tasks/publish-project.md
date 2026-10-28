---
name: publish-project
title: Publishing the project page
when: Running a project in phases
description: Publish a project page as a claude.ai artifact, with its state read again
emit: [claude]
argument-hint: "<data directory> [artifact url]"
---

Publishes the page *Building the project page* renders as a claude.ai artifact,
with its data beside it, so the next session starts from the data.

The page to publish: $ARGUMENTS

## Steps

1. Read the state again, right before publishing: `render.py` never reaches
   GitHub. For each PR item with a `url` that isn't `done` or `dropped`, read
   the PR with the GitHub tools you have, and, for one without a `url`, look
   for a PR opened from its `Branch`:
   - merged: `done`, `on` its merge day, with its `result`, what it released
     and what its *Done when* showed;
   - closed without a merge: ask the user whether it is `dropped`, with `why`,
     or replaced by a new PR;
   - still open: `open` once it waits only on the user's merge, `ready` or
     `blocked` while work remains;
   - no PR yet: it keeps its status.

   Show: each PR read, and its state.
2. Set `read_at` to now, in UTC.
3. Render with `--since`, given the data as last published, or without it on
   the first publish, which has none:

   ```bash
   python3 .agents/create-project/render.py <data directory> <out directory> \
     --since <published directory>
   ```

   Fix every problem, and fix each warning or tell the user why it stands: the
   page lists those left in its Warnings. Show: what `--since` printed, or, on
   the first publish, the line the render prints.
4. Capture the `--inline` preview, with `/take-screenshot` where the repository
   has it, or with a script of your own in a headless browser, and look at
   what changed.
5. Publish, as below, then keep a copy of the data as published, in a
   directory of its own beside the data directory: the next `--since`
   compares with it.
6. Tell the user what changed, from what `--since` printed: a correction
   first, saying what was wrong; or, on the first publish, that it is the
   first. Show: the link.

## The first publish

Publish `<out directory>/index.html` with the Artifact tool, with one generic
word as its `icon`, such as `plan`. Beside it, under the same paths, publish
each file in `phases/`, the Guides' included, and each data file as
`src/<file>`, the Brief's attachments as `src/attachments/<file>`, all with the
content type `text/plain`: the page fetches the files in `phases/`, links the
attachments, and nobody opens the rest of the data on its own.

The title is the page's own, the one the render prints: `<repo>-<objective>`,
and the project's status after it once it isn't active, such as `[archived]`.
Publish it every time, since the user finds the page by it.

## Updating

- Start from the data, not the page. Read `src/project.toml` and the phase
  files with the Artifact tool's `read` action, by path, and edit copies of
  them: the files as read are the data as last published, which `--since`
  compares with. The notes for the next session, under `[handoff]`, say what
  was in flight.
- Publish to the same `url`, with the files that changed, and `null` for a
  phase file that no longer exists.
- A session that neither published nor read the live page has to read it in
  full before it can publish over it. The page holds only the calendar, the
  phase in progress and the Agenda, so that read stays small.

## The Retrospective, alone

For a project shown outside it, once its Retrospective has its story, render it
with `--retrospective` and publish `retrospective.html` as an artifact of its
own, titled `<repo>-<objective>-retrospective`, with an `icon` such as `notes`.
It carries no data of its own: publish it again from the project's data
whenever the Retrospective changes. Whom to share it with is the user's choice.

## Before the session ends

Update `[handoff]`, the notes for the next session, and publish them, so the
next session starts where this one stopped.
