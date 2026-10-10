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
- Nine phases, always in this order, each a view the indicator at the top of
  the page switches to: Brief, Research, Analysis, Plan, Build, Verify, Reuse,
  Retrospective, For later. The page opens on the phase in progress.
- A phase is Done, Now, To come or Not needed. Not needed says why in one
  sentence; Reuse is the phase most often not needed. Build and Verify can both
  be Now: Verify starts with the first merge.
- The page shows the current state. Each publish that changes a phase adds an
  entry to that phase's changelog, at its foot, newest first, naming the
  sections it changed. A correction is an entry of its own, saying what was
  wrong.
- The page says when its state was read. Read it again right before each
  publish: a status read earlier is stale by then.
- Rendering warns about what looks stale, such as a Done phase that still holds
  an unfinished item, a decision taken that no PR carries out, a merged PR
  without its result, an item Blocked on work that is done, or a date that has
  passed. Fix each before publishing, or tell the user why it stands.

## The phases

- **Brief**: the problem, the objective, what is in scope and what is out, the
  success criteria, the repositories, and the ground rules: how the user wants
  the project run, such as who merges and which branches need asking. A ground
  rule holds until the user changes it.
- **Research**: what exists, one numbered piece at a time, and what each piece
  raises.
- **Analysis**: the decisions. Each holds its options, a recommendation with
  its reasons, and the user's answer with its date. Its card lists the PRs that
  carry it out.
- **Plan**: the PRs as approved, one at a time in each repository, each with its
  branch, what it needs first, what its merge releases, and *Done when*: what
  proves it works. The settings only the user can change. The risk register:
  each risk, and the step that closes it. The Plan stays as approved: an item
  added after the approval is an amendment, dated and saying why, and the Plan
  lists its amendments under the approval's date.
- **Build**: the live state. A board of the PRs and settings in waves, built
  from what each needs; each PR's *Result* once it merges; the questions the
  work raises; and the log.
- **Verify**: each PR's *Done when*, checked where it runs, and the Brief's
  success criteria, Met or Not met yet. Build ends with the last merge, Verify
  with the last check.
- **Reuse**: what another project can take from this one, such as a template, a
  shared rule, a shared workflow, or a page to link instead.
- **Retrospective**: written for the user's portfolio, in their voice: the
  problem, the approach and the outcome; how it was built; headline figures and
  the day they were checked; what only using it revealed; what the record
  corrected, as it was and as it is; roads not taken; the risks and how they
  closed; what it cost; what was learned; what comes next; the decision log.
  Most of it comes from the other phases.
- **For later**: each deferred item, what it waits on, and where it goes when
  that comes. Deferring an item there lets the Retrospective go ahead without
  it.

## Lessons

What was learned is a list of lessons, each an item the user reviews. A lesson
that changes how projects run says, in *Becomes*, the change it proposes to the
shared rules `agentcfg` composes. Once the user adopts it, that change waits in
For later until it ships, so the next project starts from the rule rather than
from the lesson.

## Numbers and statuses

- Numbers run for the whole project and are never reused: G for ground rules,
  SC for success criteria, R for research pieces, D for decisions, Q for
  questions, S for settings, RK for risks, C for checks, L for lessons, T for
  later work, and a prefix for each repository's PRs, such as AC-1.
- An item is Done; Open, when it waits on the user, such as a PR to merge, a
  decision to take or a setting to change; Ready, when everything it needs is
  done; Blocked, naming what it waits on; or Dropped, saying why. The page says
  each in its item's words: a decision is Taken, a PR Merged, a risk Closed.
- What an item needs is data, not prose: the board's waves come from it, and
  each card lists what needs it and what names it.
- Name an item with its number and its summary, never the number alone: the
  reader shouldn't have to look D12 up.
- The Calendar says who holds the ball: the user, for every Open item; the
  agent, for every Ready one; or a date. It holds every date the project has,
  and the notes for the next session. All of it is built from the statuses:
  never repeat a status in prose, which goes stale the next time it changes.
- One glossary per project: the terms coined for it, and the terms borrowed.

## Before a session ends

Update the notes for the next session: what is in flight, where, and what comes
next. A new session reads them, then the Brief, before anything else.

## After a merge

Confirm the merge from the PR and check what it released, as *Git flow* says.
Then start the next PR in that repository, update the page, and report.
