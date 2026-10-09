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
- Seven phases, always in this order, each a view the indicator at the top of
  the page switches to: Research, Analysis, Plan, Build, Templating,
  Retrospective, For later. The page opens on the phase in progress.
- A phase is Done, Now, To come or Not needed. Not needed says why in one
  sentence; Templating is the phase most often not needed.
- The page shows the current state. Each publish that changes a phase adds an
  entry to that phase's changelog, at its foot, newest first, naming the
  sections it changed. A correction is an entry of its own, saying what was
  wrong.
- The page says when its state was read. Read it again right before each
  publish: a status read earlier is stale by then.

## The phases

- **Research**: what exists, one numbered piece at a time, and what each piece
  raises.
- **Analysis**: the decisions. Each holds its options, a recommendation with
  its reasons, the user's answer with its date, and the PRs that carry it out.
- **Plan**: the PRs as approved, one at a time in each repository, each with its
  branch, what it waits on, what its merge releases, and *Done when*: what
  proves it works. The settings only the user can change. The risk register:
  each risk, and the step that closes it. The plan stays as approved; a change
  to it is a changelog entry.
- **Build**: the live state. A board of every PR and setting with its status,
  each PR's *Result* once it merges, the checks as they settle, and the log.
- **Templating**: whether the outcome becomes a template, and the work if it
  does.
- **Retrospective**: written for the user's portfolio, in their voice: the
  problem, the approach and the outcome; how it was built; headline figures and
  the day they were checked; what only using it revealed; what the record
  corrected, as it was and as it is; roads not taken; the risks and how they
  closed; what it cost; what was learned; what comes next; the decision log.
  Most of it comes from the other phases.
- **For later**: each deferred item, what it waits on, and where it goes when
  that comes. Deferring an item there lets the Retrospective go ahead without
  it.

## Numbers and statuses

- Numbers run for the whole project and are never reused: R for research
  pieces, D for decisions, Q for questions, S for settings, RK for risks, T for
  later work, and a prefix for each repository's PRs, such as AC-1.
- An item is Done; Open, when it waits on the user, such as a PR to merge, a
  decision to take or a setting to change; Ready, when everything it waits on is
  done; Blocked, naming what it waits on; or Dropped, saying why. The page says
  each in its item's words: a decision is Taken, a PR Merged, a risk Closed.
- Name an item with its number and its summary, never the number alone: the
  reader shouldn't have to look D12 up.
- *Waiting on you*, at the top of the page, lists every Open item. It is built
  from the statuses: never write it by hand, and never repeat a status in prose,
  which goes stale the next time the status changes.
- One glossary per project: the terms coined for it, and the terms borrowed.

## After a merge

Confirm the merge from the PR and check what it released, as *Git flow* says.
Then start the next PR in that repository, update the page, and report.
