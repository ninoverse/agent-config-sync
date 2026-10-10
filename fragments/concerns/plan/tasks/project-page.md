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
each phase's status, and write the Brief with the user. The example's comments
say what each field holds.

## Render

```bash
python3 .agents/project-page/render.py <data directory> <out directory>
```

It writes `index.html`, holding the phase in progress and the Calendar, and
`phases/<phase>.html` for each other phase with content, which the page fetches
when the reader picks that phase. `--inline` puts every phase in `index.html`,
for a preview opened from disk, where a page can't fetch a file. It needs
Python 3.11 or later, and nothing else.

It writes nothing, and names the file and the item, when:

- an id is used twice anywhere on the page, a link points at an id nothing
  has, or a `[[ref]]` or a `needs` names no item;
- a status is unknown, a Blocked item doesn't say what it waits on, a Dropped
  item doesn't say why, or a phase that is Not needed doesn't say why;
- an item's status is set both on the item and in a `[status]` table;
- `needs` loops, or a date isn't one;
- the HTML in a field doesn't nest.

It still writes the page when a state looks stale, as *Project phases* says,
and prints a warning naming it. Fix the data and render again, or tell the user
why the warning stands.

## The data

- `project.toml`: `repo` and `objective`, which make the title; `summary`;
  `read_at`, a date and time in UTC; a `[phases.<phase>]` table for each phase,
  with its `status`, its `why` when it is `not-needed`, and optionally its
  `start` and `end`; `[[event]]`s, the dates that aren't items, such as a
  scheduled run or a freeze; `[handoff]`, the notes for the next session and the
  day they were `updated`; `[[glossary]]` entries, `coined` or `borrowed`; and
  `css`, stylesheets of the project's own, beside it.
- `<phase>.toml`: an optional `intro`, then `[[section]]`s, each with an `id`, a
  `title` and a `kind`: `prose`, `table`, `items`, `board`, `results`, `log`,
  `figures` or `defs`. Then `[[changelog]]` entries, newest first, each with a
  `date`, its `text`, and `changed`, the sections and items it changed. A phase
  the user approves, such as the Plan, has `approved`, the day they did.
- An `items` section has a `type`, which sets the words its statuses take:
  `piece`, `rule`, `criterion` (Met, Not met yet), `decision` (To decide,
  Taken), `question` (To answer, Answered), `pr` (To merge, Merged), `setting`
  (To set, Set), `risk` (Open, Closed, Accepted), `check` (Waiting, Passed),
  `lesson` (To review, Adopted) or `later` (Waiting, Picked up). An item can set
  its own.
- An item is a card: an `id`, a `title`, and its `fields` as `[label, text]`
  pairs. Optionally, it has:
  - `short`, the name it goes by wherever it is linked;
  - `kind`: `major`, `minor`, `patch`, `you` or `together`;
  - `status`, with its `waits` or `why`, `on`, the day it got there, and
    `result`, once it lands;
  - `needs`, the ids of the items to finish first;
  - `due`, the day it is due;
  - `amended`, as `{ on = <date>, why = "..." }`, when it was added after its
    phase's approval;
  - `repo`, the board row it goes in;
  - `ask`, when what the user does while it is Open isn't what its type says.
- A `[status.<id>]` table sets the `status`, `on`, `waits`, `why` and `result`
  of an item kept in another phase. The Plan's items keep theirs this way in
  `build.toml`, and the Brief's success criteria theirs in `verify.toml`, so the
  earlier phase shows them as agreed, and the later one where they stand.
- A `board` with `auto = true` builds its waves from `needs`, over the item
  `types` it names, and its rows from each item's `repo`, or `rows_default`;
  `waves` subtitles each wave. Without `auto`, it takes `columns` and `row`s.
- Text is HTML, as the page shows it, and `[[D1]]` anywhere in it links to D1
  with its short title: name items that way, never by a bare number. Dates are
  TOML dates, such as `2026-10-07`.
- The Calendar is built from every date the data holds: events, the days items
  reached their status, due dates, amendments, the phases' dates, and log
  entries. Nothing in it is written by hand.
- A `prose` section can take its `body` from a `file` instead, and `prefix`
  moves that file's ids, and the links to them, under a prefix: the way to
  bring in a page that predates the kit.

## Before publishing

Open the `--inline` preview, or capture it with `/take-screenshot` where the
repository has it, and look at the phase that changed. Then publish
`index.html`, with `phases/` and the data files, as `src/`, beside it.
