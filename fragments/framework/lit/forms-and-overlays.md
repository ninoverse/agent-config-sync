---
title: Forms and overlays
scope: paths
paths:
  - "src/elements/**"
---

## Form controls

- A control that holds a value is form-associated:
  `static formAssociated = true`, `readonly #internals = this.attachInternals()`,
  and the properties `name`, `value` (or `checked`), `disabled` and `required`.
- Every change of value calls `setFormValue`, and `setValidity` reports
  `required` and any error.
- It implements `formResetCallback`, which restores the default value,
  `formDisabledCallback` and `formStateRestoreCallback`.
- It renders its own label, hint and error inside its shadow root, tied to the
  control with `<label for>`, `aria-describedby` and `aria-invalid`. The error
  carries `role="alert"`.
- Form controls and buttons delegate focus, through `delegatesFocus: true` in
  `static override shadowRootOptions`, spread over
  `LitElement.shadowRootOptions`.

## Overlays

- A modal surface is a `<dialog>` in the element's own shadow root, opened with
  `showModal()` and closed with `close()`, with `open` reflected. The focus trap
  and the inert page behind it come with `showModal()`.
- Escape fires the dialog's native `cancel`, which the element turns into a
  cancelable `<prefix>-close` with `{ reason: 'escape' }`. A click on the
  backdrop does the same with `reason: 'backdrop'`. `::backdrop` is styled
  inside the element.
- Any other floating surface, such as a popover, menu, tooltip or listbox,
  carries the `popover` attribute: `auto`, or `manual` where it must not close
  on an outside click. It opens with `showPopover()` and closes with
  `hidePopover()`, and the native `toggle` event drives
  `<prefix>-open-change` with `{ open }`.
- The trigger is a `<slot name="trigger">`, and its first assigned element is
  the anchor the surface is placed against.
- The element remembers what had focus before it opened, and gives focus back
  when it closes.
- No portals, and nothing appended to `document.body`.
- Where `showPopover` is missing, the same node renders with `position: fixed`
  inside the shadow root. One check in `src/elements/shared/` decides that for
  every element.
