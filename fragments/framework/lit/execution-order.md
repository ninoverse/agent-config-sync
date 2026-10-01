---
title: Element sequencing
scope: on-demand
when: Deciding what to build next / branching strategy
---

Elements are the unit of work here: a {{ unit }} holds many, and each PR builds
one. This adds to *Execution order*; it does not replace it.

- One element per PR, built with *Adding an element*.
- Take each element through to its commit before starting the next. Elements
  share wiring files, such as the barrel that registers them, so scaffolding
  several and then wiring them all interleaves their edits in the same files,
  with no clean way to split them back into one change per element.
- Shared infrastructure, such as the event helper or a positioning controller,
  lands with the first element that needs it, in that element's PR, never ahead
  of it.
- An element that renders another by its tag comes after it, so each PR builds
  on what is already on `main`.
