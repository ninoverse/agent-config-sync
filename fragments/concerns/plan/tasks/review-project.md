---
name: review-project
title: Reviewing a project
when: Running a project in phases
description: Review a project run in phases with fresh eyes, for errors its render can't catch
argument-hint: "<data directory>"
---

Double-checks a project as someone who didn't write it, for what the render
can't check: whether what the data says is right, not only well formed.

The project: $ARGUMENTS

## Steps

1. Review it from outside the session that wrote it, where you can: a new
   session, or a sub-agent given only the data directory, *Project phases* and
   *Building the project page*, with the repositories the project works on to
   read, and none of the discussion behind them. What the author knows but
   didn't write is what the page's readers miss too.
2. Render it, as *Building the project page* says. Show: each problem and each
   warning.
3. Read each phase against *Project phases*:
   - the Brief: does each success criterion say what is measured, and is each
     verified by a check? Do its attachments hold what each is measured
     against, and does it say where the project comes from? Does the scope cover the objective,
     and no more?
   - the Research: does each piece raise something an item takes up?
   - the Analysis: does each decision list its options, with the reasons for
     the one recommended, none of them made up, or propose one alone, saying
     why only it? Does a PR, a setting or a task carry it out?
   - the Plan: does each PR say its branch, what it needs first and its kind,
     with a *Done when* a check can prove, and each task its *Done when*? Does
     each success criterion have a check, and each check the PR it needs, or
     that needs it? Is each risk one that hasn't happened, with the step that
     closes it?
   - Execution and Verify: does each status match what GitHub says, and each
     result what the PR did?
   - Deferred: does each item say what it waits on, and where it goes then?
4. Read it as a newcomer: could a session that never saw the project carry it
   on from the notes and the Brief alone? Is a fact said twice, or an item
   named without its link?
5. List the findings, numbered, each with where it is, what is wrong and the
   fix you propose. A reviewer apart from the session reports them to it and
   changes nothing.
6. Act on each, as the session that keeps the project, in the data and never
   in the chat alone, since the user reads the page: fix what is plainly
   wrong; put what is the user's to settle on the page, as a decision, or a
   question once Execution has started, proposed alone where one way is
   worth taking; and leave, saying why, what isn't worth its fix. Then
   publish with `/publish-project`. Show: each finding in a line, with what
   became of it, and the items the user now has to answer, each by the name
   of its page and its phase.
