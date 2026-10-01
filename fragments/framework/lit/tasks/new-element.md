---
name: new-element
title: Adding an element
when: Adding or modifying an element
description: Add an element following the 6-step element workflow
argument-hint: "<element-name> [one-line description of what it does]"
---

The exact procedure for adding or modifying a single element. Follow every step
in order; do not skip or reorder.

The element to add: $ARGUMENTS

---

## Pre-flight

Before writing any code:

1. **Ask for confirmation.** State which element you are about to add and what
   it is for. Wait for explicit approval. Do not start on your own initiative.

2. **Check whether it exists:**
   ```bash
   ls src/elements/<name>/ 2>/dev/null && echo EXISTS || echo MISSING
   ```
   If it exists, report what is there and ask: skip / overwrite / modify. Never
   silently overwrite. This is also how an interrupted run resumes: modify, from
   the first step whose file is missing.

3. **Find the tag prefix.** Every element in `src/elements/` shares one. With no
   element there yet, ask for it.

4. **The API table.** Write the element's table as *Element API table* lays it
   out, and wait for approval; if the request brought an approved table, use
   that one. The table is the contract for every step below: each row becomes a
   property, slot, event or part, and nothing outside it does.

Then read *Elements* and *Element styles*, and *Forms and overlays* for a form
control or an overlay. They load on their own once a file under `src/elements/`
is read, which is too late for the first file this task writes.

---

## 6-step checklist (one element)

The templates are in `.agents/new-element/`. In each, replace `<prefix>` and
`<name>` with the tag prefix and the element's kebab-case name, and `<Prefix>`
and `<Name>` with their PascalCase forms. The templates show one of each kind of
member; delete whatever the approved table doesn't call for.

### 1. The element

Copy `element.ts.tpl` to `src/elements/<name>/<name>.ts`.

- One property per property row, with its type, default and JSDoc line, and
  `reflect` where CSS selects on it.
- A `<slot>` per slot row and a part per part row, with the class JSDoc's
  `@slot` and `@csspart` lines to match.
- Per event row, an exported `<Name><Event>Detail` interface, an `@fires` line,
  and a call to `emit`. If `src/elements/shared/events.ts` doesn't exist yet,
  this element brings it: copy `events.ts.tpl` there.

### 2. Styles

Copy `element.styles.ts.tpl` to `src/elements/<name>/<name>.styles.ts`. `:host`
gets its `display` first, every inner node with a size gets one too, and
colours and spacing come from the design tokens.

### 3. Browser tests

Copy `element.test.ts.tpl` to `src/elements/<name>/<name>.test.ts`, with the
blocks *Element tests* lists, in its order: one `reflects` block per reflected
property, one `dispatches` block per event, one `projects` block per slot. The
form block stays only for a form control.

### 4. Server-render test

Copy `element.ssr.test.ts.tpl` to `src/elements/<name>/<name>.ssr.test.ts`.

### 5. Verification gate

If `.agents/new-element.local.md` exists, follow it now, before the gate. It
holds the steps this repository adds to this checklist, such as the other files
an element needs and where it is registered; it is written by hand, and
`agentcfg` leaves it alone.

Then {{ gates }} must pass, with {{ gates_clean }}, before committing:

```bash
{{ gate_command }}
```

### 6. Commit, then hand the PR over

```
feat(<scope>): add <name> element
```

Commit and hand the PR over as *Git flow* and *PR instructions* say, with the
approved API table in its description.

---

## Before committing

Points that are easy to get wrong, so verify each one:

- Every row of the approved API table is in the element, and nothing else is.
- `:host` has a `display`, and so does every inner node with a size.
- Booleans reflect presence, and arrays and objects are `attribute: false`.
- The browser tests have the blocks *Element tests* lists, in its order, and the
  server-render test runs in Node.
- `.agents/new-element.local.md` was followed, if it exists.
- `{{ gate_command }}` passes before you commit.
