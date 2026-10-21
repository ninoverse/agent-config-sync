---
name: create-project
title: Building the project page
when: Running a project in phases
description: Start a project run in phases, and build its page from TOML data
argument-hint: "<data directory> [out directory]"
---

Starts a project as *Project phases* describes, and builds its page from TOML
files, checked before anything is published. Every skill that runs a project
renders its page this way: this is the kit's reference, for its checks and its
data.

The project: $ARGUMENTS

## Steps

1. Agree the page's name with the user, `<main repository>-<objective>`, and
   the repositories the project involves. Show: the name.
2. Copy the example outside the repository. A project's data is its own record,
   published beside its page, and not part of any repository:

   ```bash
   cp -r .agents/create-project/example <data directory>
   ```

   Set `repo`, `objective`, `summary` and `read_at` in `project.toml`, and each
   phase's status: one not needed says why, and one that starts before those it
   follows are done says why, in `early`. The example's comments say what each
   field holds.
3. Write the Brief with the user, discussing it before anything is written: the
   problem, the objective, the scope, the success criteria, each with how it is
   checked, the repositories and the ground rules. Keep the criteria's statuses
   in `verify.toml`, under `[status]`, so the Brief shows them as agreed.
4. Render it, as below. Fix every problem, and fix each warning or tell the user
   why it stands. Show: the line the render prints, and each warning left.
5. Look at each phase with content at a laptop's width and a phone's, in the
   `--inline` preview, or with `/take-screenshot` where the repository has it.
6. Publish it with `/publish-project`.

## Render

```bash
python3 .agents/create-project/render.py <data directory> <out directory>
```

It writes `index.html`, holding the calendar, who holds the ball, the phase in
progress and the Agenda, and `phases/<phase>.html` for each other phase with
content, which the page fetches when the reader picks that phase. A phase
without content has a tab that doesn't open. Each item's card shows its number,
summary and chips, and opens on a click, or a link to it, to its fields; and
the calendar counts each day's items by what happened to them, such as 18
merged.
`phases/guides.html` is the Guides: the guide to using the page, from
`guide.html` beside the renderer, with its tables built from the renderer's own
words, then the glossary. `--inline` puts every phase in `index.html`, for a
preview opened from disk, where a page can't fetch a file. `--retrospective`
writes `retrospective.html` instead: the Retrospective alone, without the tabs,
the calendar or the Agenda, naming as text the items it doesn't hold. A link
written by hand to one of those fails the render there. It needs Python 3.11 or
later, and nothing else.

Under the line that says what it wrote, it prints where the project stands, as
the page's header shows it: each phase that is Now, with how far it is, and who
holds the ball.

It writes nothing, and names the file and the item, when:

- no phase has content yet;
- an id doesn't start with its type's letters, which *Project phases* lists,
  or a PR's starts with another type's rather than its repository's prefix;
- an id is used twice anywhere on the page, a link points at an id nothing
  has, or a `[[ref]]` or a `needs` names no item;
- a status is unknown, a Blocked or Deferred item doesn't say what it waits
  on, a Blocked one waits on `owner`, which makes it Open, a Dropped item
  doesn't say why, one To be moved doesn't name its project in `to`, or a
  Moved one doesn't link its card there in `to`; or a phase that is Not
  needed doesn't say why, or has a `<phase>.toml`: its tab doesn't open, so
  nothing in it would show;
- a phase starts before those it follows are done, or before the day they
  end, or Build before the Plan's approval, without `early` saying why; the
  Plan is done without `approved`; a phase ends before one it runs beside,
  such as Reuse before Build; or is Build or Verify, and done while it holds
  an unfinished item, which reopens it;
- a decision isn't taken, or deferred, once the Plan is approved, unless it
  was amended in on the day of the approval or after; or Build has started
  while the Brief has no success criterion, but dropped ones;
- a PR's card has no `Branch` field, or no `Done when`: the owner approves
  each PR with its branch, and Verify checks what its *Done when* says;
- an item that isn't a risk is `happened`, or a risk that is doesn't name what
  took it over, in `result`, or was amended in after the day it happened;
- an item's status is set both on the item and in a `[status]` table;
- an item is in a phase that doesn't hold its type, the Analysis or the Plan
  has a section other than `items`, Build one other than a `board`, `results`
  or `items`, Verify one other than `items` or `results`, or Reuse one other
  than `defs`; or a phase other than the Retrospective has a part it builds;
- a section shows nothing but its title, such as a card section with no
  cards; a Results section with nothing to show yet says so instead;
- `needs` loops, or a date isn't one;
- the HTML in a field doesn't nest.

It still writes the page, prints a warning naming the file and the item, and
lists it in the page's Warnings, which opens beside the Agenda and the Guides,
with how many there are, when:

- a state looks stale, as *Project phases* says;
- text names an item by its number alone rather than its `[[ref]]`, outside a
  `short`, which can't hold a link, and a link written by hand;
- a link takes a possessive, such as `[[HMI-8]]'s`, which reads as its short
  title's;
- a question in Build is dated before Build started: one asked before the
  Plan's approval is a decision;
- a decision has no `options`, as one recorded after the fact may not;
- two PRs in one repository are in progress at once: open on GitHub, as
  their `url` says, and not done;
- an adopted lesson with a `Becomes` field and nothing in Deferred or the Plan
  name each other, though its change waits there until it ships;
- with `--since`, which renders for a publish, `read_at` is more than 15
  minutes before the render: the page would show a state that may have
  changed;
- an item has `stands`, but no warning about it to stand.

Fix the data and render again, or tell the user why the warning stands. Once
they agree it stands, say why on its item, in `stands`: the render then prints
its warnings apart, each with why, and the page's Warnings list them under a
heading of their own.

`--since <directory>`, given the data as it was last published, also prints
what has changed in each phase since, statuses in their type's words. It
writes nothing when an item is gone, since an item is never deleted, but
`dropped`, with `why`; or when an item is new in the Brief, the Research, the
Analysis or the Plan, which the published data had done, or approved, and
doesn't say it is an amendment, with `amended`.

## The data

- `project.toml`: `repo` and `objective`, which make the title; `summary`;
  `read_at`, a date and time in UTC; a `[phases.<phase>]` table for each phase,
  with its `status`, its `why` when it is `not-needed`, and optionally its
  `start` and `end`, `early`, why it started before those it follows were
  done, and `reopened`, as `[{ ended = <date>, on = <date> }]`, each time it
  ended and later reopened; `[[event]]`s, the dates that aren't items, such
  as a scheduled run or a freeze, with `automated = true` on a run that starts
  on its own, which the page marks Automated; `[handoff]`, the notes for the
  next session and the day they were `updated`; `[[glossary]]` entries, each
  a `term`, its `text` and its `source`, `coined` or `borrowed`; and `css`,
  stylesheets of the project's own, beside it.
- `<phase>.toml`: `[[section]]`s, each with an `id`, a `title` and a `kind`:
  `prose`, `table`, `repos`, `items`, `board`, `results`, `figures` or `defs`;
  or, in the Retrospective, one of the parts it builds from the other phases,
  below.
  A section that carries on the one before it can go without a `title`, and
  `--since` then names it by that section's. A phase the user approves, such
  as the Plan, has `approved`, the day they did. A section that shows a table,
  such as a `table`, `repos` or `board`, takes `min_width`, the width in
  pixels below which it scrolls sideways rather than squeeze its columns.
- An `items` section has a `type`, which sets the words its statuses take:
  `piece`, `rule`, `criterion` (Met, Not met yet), `decision` (To decide,
  Taken), `question` (To answer, Answered), `pr` (To merge, Merged), `setting`
  (To set, Set), `risk` (Open, Closed, Accepted, Happened), `check` (Waiting,
  Passed), `lesson` (To review, Adopted) or `deferred` (Waiting, Picked up). An
  item can set its own.
- An item is a card: an `id`, a `title`, and its `fields` as `[label, text]`
  pairs, where a text that holds several things, such as the decisions a PR
  carries out, is a list of them, shown as a list. A text that is one
  `<span class="pill ...">` and nothing else, such as what a comparison found,
  shows as a chip instead, so a folded card shows it. Optionally, it has:
  - `short`, the name it goes by wherever it is linked;
  - `stands`, why its warnings stand, by the user's choice;
  - `kind`: `major`, `minor`, `patch` or `owner`;
  - `status`, with its `waits` or `why`, `on`, the day it got there, and
    `result`, once it lands: `open`, `ready`, `blocked`, `done` or `dropped`;
    `happened`, for a risk; or, for any item, `deferred`, `to-move`, with the
    project that takes it in `to`, or `moved`, with its card's address there
    in `to`. A deferred item's `waits` is `owner` when it waits on the user's
    go, or their call on a question or a decision, which its card shows as
    theirs, and the header counts under them;
  - `from`, on an item moved in from another project, its card's address on
    that project's page;
  - `url`, the PR's address once it is open, where its state is read from;
  - `needs`, the ids of the items to finish first; a success criterion's are
    the checks that prove it, which its card shows as Verified by; a PR's can
    be the checks of its branch, which it waits on before it merges;
  - `options`, as `[key, text]` pairs, with `recommended` and `chosen` naming
    one each by its key: a decision's choices, shown as a list that marks the
    recommended one until one is chosen, and then only the chosen one;
  - `amended`, as `{ on = <date>, why = "..." }`, when it was added after its
    phase's approval, or after its end in a phase without one, which lists it
    at its end under that day and `why`, and whose tab then reads Amended;
  - `repo`, the board row it goes in;
  - `ask`, when what the user does while it is Open isn't what its type says,
    which its chip and the calendar then say instead: a PR with `ask = "Test"`
    reads To test, not To merge.
- A `repos` section lists the repositories, each a `[[section.repo]]` with its
  `name`, its `use`, `change`, `read` or `new`, shown as a chip, and its
  `part`.
- A `[status.<id>]` table sets the `status`, `on`, `waits`, `why` and `result`
  of an item kept in another phase. The Plan's items keep theirs this way in
  `build.toml`, and the Brief's success criteria theirs in `verify.toml`, so the
  earlier phase shows them as agreed, or To agree until the user agrees them,
  and the later one where they stand.
- A `board` with `auto = true` builds its waves from `needs`, over the item
  `types` it names, and its rows from each item's `repo`, or `rows_default`;
  `waves` subtitles each wave. Without `auto`, it takes `columns`, as
  `[title, subtitle]` pairs, and `[[section.row]]`s, each a `name` and its
  `cells`, a list of ids for each column. Either way, `rows_title` heads the
  column of row names, and it opens at its first column with an unfinished
  item.
  A `results` section in the same phase leaves out what the board shows until
  it has a `result`, and then shows the result alone, or until it moves, and
  then shows the link to its new page.
- A `defs` section is one card of `[[section.def]]`s, each a `term` and its
  `text`, such as the Brief's project. In Reuse, each term is a card of its
  own, titled by it: a piece another project can take. So is a definition
  with `fields`, `[label, text]` pairs in place of its `text`, such as what
  only using it revealed: Expected, Observed, Changed.
- The Retrospective builds its record from the other phases, in sections of
  their own kinds: `timeline`, how each phase went, with a line for each in
  `lines`, keyed by the phase; `roads`, every item dropped, with why; `risks`,
  each risk and how it ended; `cost`, what the data counts of what it took,
  then `rows`, `[label, text]` pairs for what it can't; `next`, what waits, by
  who or what starts it; and `decisions`, every decision with the option
  chosen. One with nothing to list says so.
- A `figures` section with `auto = true` starts with what the data counts: PRs
  merged, releases, decisions taken, settings changed by hand, lessons adopted,
  and the days from the first date to the last. Its `figure`s follow, each a
  `value` and its `label`. A `note` under them says where they come from; with
  `auto` and no `note`, it gives the day they were counted.
- A `table` section has `head`, its column titles, and `rows`, each a list of
  its cells.
- Text is HTML, as the page shows it, and `[[D1]]` anywhere in it links to D1
  with its short title: name items that way, never by a bare number, and put
  the link after its noun, as in "the merge of `[[HMI-8]]`". Dates are TOML
  dates, such as `2026-10-07`.
- The calendar and the Agenda are built from every date the data holds: events,
  the days items reached their status, amendments, and the phases' dates.
  Nothing in them is written by hand.
- A `prose` section's `body` is set at reading width, or across the page with
  `wide = true`. It can take its `body` from a `file` instead, and `prefix`
  moves that file's ids, and the links to them, under a prefix: the way to
  bring in a page that predates the kit.