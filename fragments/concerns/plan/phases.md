---
title: Project phases
scope: on-demand
when: Running a project in phases
---

A project that takes more than one PR, or more than one repository, runs in
phases, and one page tracks it: the project page, which `/project-page` builds.
Each phase starts with a discussion with the user, and nothing is written before
they answer.

## The page

- One page per project, named `<main repository>-<objective>`, such as
  `hmi-components-agentcfg-adoption`. The name is settled when the project
  starts, and kept.
- Nine phases, each a view the indicator at the top of the page switches to,
  in two groups. The first six run in this order, numbered: Brief, Research,
  Analysis, Plan, Build, Verify. The other three, unnumbered, are what the
  project leaves: Reuse, the Retrospective and Deferred. The page opens on the
  phase in progress. Above the indicator, on every view, are the calendar and
  who holds the ball. Two views aren't phases, and open over the page from its
  top right: the Agenda, and the Guides, which say how to use the page, chips
  and sections included, and hold the glossary.
- A phase is Done, Now, To come or Not needed. Not needed says why in one
  sentence, in the data; Reuse is the phase most often not needed. A tab opens
  only once its phase has something to show, so the tab of a phase not needed,
  or not written yet, doesn't open. Build and Verify can both be Now: Verify
  starts with the first merge. A phase that is Now shows on its tab how many
  of its items are done, and Deferred's tab how many items wait.
- The phases run in order: each starts once the one before it is Done or Not
  needed, but Verify and Reuse, which start once Build has. One that starts
  early says why, and the Agenda shows it on the day it started. A phase that
  runs beside others ends only after them, never early: Verify after Build,
  Reuse after both, and the Retrospective after every other. Build and Verify
  reopen when new work comes in, and keep the day each ended and the day it
  reopened.
- The page shows the current state, and the Agenda what happened, by day.
  Each publish, tell the user what changed since the last, as rendering
  against the data as last published lists it: a correction first, saying
  what was wrong.
- The page says when its state was read. Read it again right before each
  publish, each PR from GitHub: a status read earlier is stale by then.
- Rendering warns about what looks stale, such as a Done phase that still holds
  an unfinished item, a decision taken that no PR carries out or with no option
  chosen, a merged PR without its result, or an item Blocked on work that is
  done. Fix each before publishing, or tell the user why it stands.

## The phases

- **Brief**: the problem, the objective, what is in scope and what is out, the
  success criteria, each with the checks that verify it, the repositories, each
  with what the project does with it (changes it, reads it, or creates it), and
  the ground rules: how the user wants the project run, such as who merges and
  which branches need asking. A ground rule holds until the user changes it.
- **Research**: what exists, one numbered piece at a time, and what each piece
  raises.
- **Analysis**: the decisions, and nothing else. Each lists its options, with
  the reasons for the one recommended. Until the user answers, the page marks
  that one; after, only the one chosen, with the date. Its card lists the PRs
  and settings that carry it out. One list is the default; only when the
  decisions are many do they come in batches, one section each, answered
  together, which the page lists at the top. The evidence behind them, such
  as a comparison or a measurement, goes in the Research, and the decisions
  link to it.
- **Plan**: its cards and nothing else, which the page lists at the top. The
  PRs as approved, one at a time in each repository, each with its
  branch, what it needs first, what its merge releases, as its kind, and *Done
  when*: what proves it works. The settings only the user can change. The risk
  register: each risk, written before what it describes can happen, and the
  step that closes it. The Plan stays as approved: an item added after the
  approval is an amendment, dated and saying why, and the Plan ends with its
  approval: the day, and its amendments by day and why.
- **Build**: the live state. A board of the PRs and settings in waves, built
  from what each needs; each PR's *Result* once it merges; and the questions
  the work raises, and nothing else. What happened is in the Agenda, so Build
  keeps no log of its own.
- **Verify**: each PR's *Done when*, checked where it runs, and the Brief's
  success criteria, Met or Not met yet, and nothing else. A check's title says
  how it is checked: what it proves is already on the PR it needs and the
  criterion it verifies. Build ends with the last merge, Verify with the last
  check.
- **Reuse**: what another project can take from this one, such as a template, a
  shared rule, a shared workflow, or a page to link instead, and nothing else:
  each piece a card, saying what it is, how to take it, and the items that
  built it.
- **Retrospective**: written for the user's portfolio, in their voice: the
  problem, the approach and the outcome; how it was built; headline figures and
  the day they were checked; what only using it revealed; what the record
  corrected, as it was and as it is; roads not taken; the risks and how they
  closed; what it cost; what was learned; what comes next; the decision log.
  Most of it comes from the other phases, and the figures are counted from the
  data wherever they can be. It also renders alone, as a page the user can
  share.
- **Deferred**: its deferred work and questions, and what other phases have
  set aside, each with what it waits on and where it goes when that comes.
  Deferring an item lets the Retrospective go ahead without it.

## Lessons

What was learned is a list of lessons, each an item the user reviews. A lesson
that changes how projects run says, in *Becomes*, the change it proposes to the
shared rules `agentcfg` composes. Once the user adopts it, that change waits in
Deferred until it ships, so the next project starts from the rule rather than
from the lesson.

## Numbers and statuses

- Numbers run for the whole project and are never reused: G for ground rules,
  SC for success criteria, R for research pieces, D for decisions, Q for
  questions, S for settings, RK for risks, C for checks, L for lessons, T for
  deferred work, and a prefix for each repository's PRs, such as AC-1.
- Each item lives in its phase: ground rules and success criteria in the
  Brief, research pieces in the Research, decisions in the Analysis, PRs,
  settings and risks in the Plan, questions in Build, checks in Verify,
  lessons in the Retrospective, and deferred work and questions in Deferred.
- An item is Done; Open, when it waits on the user, such as a PR to merge, a
  decision to take or a setting to change; Ready, when everything it needs is
  done; Blocked, naming what it waits on; or Dropped, saying why. The page says
  each in its item's words: a decision is Taken, a PR Merged, a risk Closed.
  An item is never deleted: one that no longer belongs is Dropped.
- A risk that comes true is Happened, naming the question or the blocker that
  took it over: it is no longer a risk. What has already happened is never
  written as a risk.
- Any item can be set aside: Deferred, parked until a trigger outside the
  project, which it names, or until the user says, which the page marks as
  theirs; To be moved, once the user decides another project takes it, naming
  that project; or Moved, once that project's page has it, linking its card
  there, which links back. An item set aside no longer holds its phase open,
  and Deferred lists it until it moves.
- What an item needs is data, not prose: the board's waves come from it, and
  each card lists what needs it and what mentions it.
- Name an item with its number and its summary, never the number alone: the
  reader shouldn't have to look D12 up. Since the summary follows the number,
  put the name after its noun, as in "the merge of HMI-8", never in a
  possessive.
- Under the calendar, the page says who holds the ball: the owner, the user
  who decides, merges and changes settings, for every Open item, with how many
  are deferred until they say; the agent, for every Ready one; or a date coming
  up, with an automated run marked as such. The Agenda holds every date the
  project has, ahead and past, and the notes for the next session. All of it
  is built from the statuses: never repeat a status in prose, which goes stale
  the next time it changes. Say each fact once: a field doesn't repeat a chip,
  such as a PR's kind, nor a card another card.
- One glossary per project: the terms coined for it, and the terms borrowed. It
  sits in Guides, after the guide to using the page.

## Before a session ends

Update the notes for the next session: what is in flight, where, and what comes
next. A new session reads them, then the Brief, before anything else.

## After a merge

Confirm the merge from the PR and check what it released, as *Git flow* says.
Then start the next PR in that repository, update the page, and report.
