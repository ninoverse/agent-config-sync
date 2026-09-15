# PR Guidelines

## Title

Follow the same format as commit messages: `<type>(<scope>): <description>`.  
Keep it under 72 characters.

## Description template

```markdown
## What
<!-- One-paragraph summary of the change -->

## Why
<!-- Motivation: bug, feature request, refactor reason -->

## How
<!-- Non-obvious implementation decisions -->

## Testing
<!-- How was this manually verified? Screenshots for UI changes. -->
```

## Rules

- One logical change per PR, in **one commit**; split unrelated work into separate PRs
- Branch from an up-to-date `main`, so no rebase is needed before review
- `just ci` must pass before the branch is pushed — all four gates, zero warnings
- Link to the relevant section in CLAUDE.md or a `.claude/` rule file if the PR establishes a new pattern

## Size guidance

| Lines changed | Action |
|--------------|--------|
| < 200 | Normal review |
| 200 – 600 | Add context in the description about where to start reading |
| > 600 | Consider splitting — or at minimum call it out and justify it |

## Who opens the PR

Claude pushes the branch and outputs the title and description, then stops. The
user opens and merges the PR. See `.claude/git-flow.md` for the full loop.

Because a branch is only pushed once the gates already pass, there is no
work-in-progress state to represent — draft PRs are not used.
