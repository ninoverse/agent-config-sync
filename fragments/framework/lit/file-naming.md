---
title: Element files
scope: on-demand
when: Creating new files
---

## Layout

| Path | Contents |
|------|----------|
| `src/elements/<name>/` | One element, in the four files below |
| `src/elements/shared/` | What several elements use: the event helper, shared styles, DOM helpers |

| File | Holds |
|------|-------|
| `<name>.ts` | The element's class |
| `<name>.styles.ts` | Its styles, as one `css` tagged template |
| `<name>.test.ts` | Its browser tests |
| `<name>.ssr.test.ts` | Its server-render test, run in Node |

## Naming

Everything derives from one kebab-case name and the tag prefix every element in
this repository shares.

| Item | Form | Example, with the prefix `my` |
|------|------|-------------------------------|
| Folder and files | kebab-case | `src/elements/date-picker/date-picker.ts` |
| Tag | `<prefix>-<name>` | `my-date-picker` |
| Class | the tag in PascalCase | `MyDatePicker` |
| Events | `<prefix>-<event>` | `my-open-change` |
| Event detail types | `<Name><Event>Detail` | `DatePickerOpenChangeDetail` |
| Attributes, slots and parts | kebab-case | `min-date`, `trigger`, `base` |
