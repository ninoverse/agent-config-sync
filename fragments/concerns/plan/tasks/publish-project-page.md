---
name: publish-project-page
title: Publishing the project page
when: Running a project in phases
description: Publish or update a project page as a claude.ai artifact
emit: [claude]
argument-hint: "<out directory> [artifact url]"
---

Publishes the page `/project-page` built as a claude.ai artifact, with its data
beside it, so the next session starts from the data.

The page to publish: $ARGUMENTS

## The first publish

Publish `<out directory>/index.html` with the Artifact tool, with one generic
word as its `icon`, such as `plan`. Beside it, under the same paths, publish
each `phases/<phase>.html` and each data file as `src/<file>`, all with the
content type `text/plain`: the page fetches the phase files, and nobody opens
the data on its own.

The title is the page's own, `<repo>-<objective>`. Keep it on every publish,
since the user finds the page by it.

## Updating

- Start from the data, not the page. Read `src/project.toml` and the phase
  files with the Artifact tool's `read` action, by path, edit them, and render
  again.
- Read the project's state again right before publishing, and set `read_at` to
  that time.
- Publish to the same `url`, with the files that changed, and `null` for a
  phase file that no longer exists.
- A session that neither published nor read the live page has to read it in
  full before it can publish over it. The page holds only the phase in
  progress, so that read stays small.

## Hand it over

Give the user the link, and say in one sentence what changed.
