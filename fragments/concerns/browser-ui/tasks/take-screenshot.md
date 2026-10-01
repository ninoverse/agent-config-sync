---
name: take-screenshot
title: Taking a screenshot
when: Capturing what a page renders
description: Capture a rendered page, or one section of it, as a PNG
argument-hint: "<url> [section heading] [out.png]"
---

Captures what a page renders, as a PNG a reviewer can look at. *Visual check*
says when a PR needs one.

The capture to take: $ARGUMENTS

## Run it

From the repository root, with the page being served:

```bash
sh .agents/take-screenshot/screenshot.sh <url> "<section heading>" <out.png>
```

- `<url>` is the page as the repository serves it locally: its dev server, or a
  `file://` URL for a static page.
- `"<section heading>"` is the text of an `<h2>`, and the capture is the
  `<section>` around it. `""` captures the whole page.
- `<out.png>` goes outside the repository, such as in a temporary directory, so
  a capture never lands on `main`.
- `--clip-children`, last, clips to the section's children instead of its box.

The viewport is 1000 × 900 CSS px, at 2× scale. Show the image to the reviewer
in the session.

## What to capture

- A section, as a rule. A long page captured whole is complete but too tall to
  review by eye; the whole page suits a short page, or a comparison by pixel
  diff.
- A section whose `display` is `contents` has no box of its own, so its children
  are clipped instead, with or without `--clip-children`.

## What it prints

- `take-screenshot: using <entry>` on stderr: the entry that took the capture,
  which the visual-check record names.
- `wrote <out.png>` when it succeeds.
- A warning naming each web font that failed to load. The capture then shows a
  fallback face, which changes the layout as well as the letters, so say so in
  the record and never compare it with a capture whose fonts loaded.

## When it can't run

- Exit code 2 means no entry fits this machine, and the dispatcher lists what
  each one needs. Report that list; do not install anything to make an entry
  fit.
- Any other failure is the entry's own error, such as a heading the page
  doesn't have. Fix the arguments rather than reaching for another entry.
- Where `sh` is missing, run the entry whose needs hold directly, with the same
  arguments: `node .agents/take-screenshot/playwright.mjs <url> …`.

## The entries

The dispatcher runs the first entry whose needs hold, in this order:

| Entry | Needs |
|-------|-------|
| `playwright` | `node`; the `playwright` package resolving from the repository root; Chromium where Playwright installed it, or at `/opt/pw-browsers/chromium` |
