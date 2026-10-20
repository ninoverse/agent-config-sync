---
name: split-project
title: Splitting a project
when: Running a project in phases
description: Move part of a project run in phases into a new project, with a page of its own
argument-hint: "<page> <new objective>"
---

Moves part of a project into a new one, as *Project phases* says of an item To
be moved: each moved item keeps its card on the old page, linking the new one,
which links back.

The project, and the new one: $ARGUMENTS

## Steps

1. Agree with the user the new project's name, `<main repository>-<objective>`,
   and what moves to it. Its numbers start again: each moved item gets a new
   one, and its card links its old one. Show: each item that moves, with its
   old number and its new.
2. In the source's data, mark each item that moves `to-move`, with `to` naming
   the new project.
3. Create the new project with `/create-project`, its data holding what moves.
   Each moved item takes its new number, and `from`, its old card's address:
   `<source page url>#<old id in lower case>`. In moved text, a reference to an
   item that moved takes its new number; one to an item that stays becomes a
   link to its card on the source page, with its number and its summary.
4. Publish the new project with `/publish-project`: its address is now known.
   Show: its link.
5. In the source's data, mark each moved item `moved`, `on` the day, with `to`,
   its new card's address: `<new page url>#<new id in lower case>`. Update the
   notes for the next session on both projects.
6. Publish the source with `/publish-project`. Files published beside the
   source page that belong to the new project move with it.
