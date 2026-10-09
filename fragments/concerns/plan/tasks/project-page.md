---
name: project-page
title: Building the project page
when: Running a project in phases
description: Build or update a project's page from its TOML data, and check it
argument-hint: "<data directory> [out directory]"
---

Builds the page *Project phases* describes, from TOML files, and checks it
before anything is published.

The project: $ARGUMENTS

## Start a project

Copy the example outside the repository. A project's data is its own record,
published beside its page, and not part of any repository:

```bash
cp -r .agents/project-page/example <data directory>
```

Then set `repo`, `objective`, `summary` and `read_at` in `project.toml`, and
each phase's status. The example's comments say what each field holds.

## Render

```bash
python3 .agents/project-page/render.py <data directory> <out directory>
```

It writes `index.html`, holding the phase in progress, and
`phases/<phase>.html` for each other phase with content, which the page fetches
when the reader picks that phase. `--inline` puts every phase in `index.html`,
for a preview opened from disk, where a page can't fetch a file. It needs
Python 3.11 or later, and nothing else.

It writes nothing, and names the file and the item, when:

- an id is used twice anywhere in the project, a link points at an id nothing
  has, or a `[[ref]]` names no item;
- a status is unknown, a Blocked item doesn't say what it waits on, a Dropped
  item doesn't say why, or a phase that is Not needed doesn't say why;
- an item's status is set both on the item and in a `[status]` table;
- the HTML in a field doesn't nest.

## The data

- `project.toml`: `repo` and `objective`, which make the title; `summary`;
  `read_at`; a `[phases.<phase>]` table for each phase, with its `status` and,
  when it is `not-needed`, `why`; `[[glossary]]` entries, `coined` or
  `borrowed`; and `css`, stylesheets of the project's own, beside it.
- `<phase>.toml`: an optional `intro`, then `[[section]]`s, each with an `id`, a
  `title` and a `kind`: `prose`, `table`, `items`, `board`, `results`, `log`,
  `figures` or `defs`. Then `[[changelog]]` entries, newest first, each with a
  `date`, its `text`, and `changed`, the sections and items it changed.
- An `items` section has a `type`, which sets the words its statuses take:
  `piece`, `decision` (To decide, Taken), `question` (To answer, Answered), `pr`
  (To merge, Merged), `setting` (To set, Set), `risk` (Open, Closed), `check`
  (Waiting, Passed) or `later` (Waiting, Picked up). An item can set its own.
- An item is a card: an `id`, a `title`, its `fields` as `[label, text]` pairs,
  and optionally a `short` title, which names it wherever it is linked, a
  `kind` (`major`, `minor`, `patch`, `you` or `together`), a `status` with its
  `waits` or `why`, and an `ask`, when what the user does while it is Open isn't
  what its type says.
- A `[status.<id>]` table sets the status, and the `result`, of an item kept in
  another phase. The Plan's PRs keep theirs this way in `build.toml`, so the
  Plan shows them as approved and the Build shows where they stand.
- Text is HTML, as the page shows it, and `[[D1]]` anywhere in it links to D1
  with its short title: name items that way, never by a bare number.
- A `prose` section can take its `body` from a `file` instead, and `prefix`
  moves that file's ids, and the links to them, under a prefix: the way to
  bring in a page that predates the kit.

## Before publishing

Open the `--inline` preview, or capture it with `/take-screenshot` where the
repository has it, and look at the phase that changed. Then publish
`index.html`, with `phases/` and the data files, as `src/`, beside it.
