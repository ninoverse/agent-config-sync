# Git Flow

The branch → commit → PR loop for **every** change in this repository. There is
one flow; it applies to tooling, docs, config and crates alike.

The defining constraint: **no stacked PRs.** Each branch is cut from an
up-to-date `main` and is merged before the next one is cut. Only one branch is
ever in flight.

---

## The loop

```bash
# 1. Start from an up-to-date main
git switch main
git pull --ff-only

# 2. Cut the branch (format: .claude/branch-naming.md)
git switch -c <type>/<short-description>

# 3. Make the change, then run the gates
just ci                              # all four gates; see .claude/testing-requirements.md

# 4. One commit (format: .claude/commit-conventions.md)
git add <the files this change touches>
git commit

# 5. Push
git push -u origin <type>/<short-description>
```

**6. Output the PR title and description, then STOP.**

Use the template in `.claude/pr-guidelines.md`. Do not open the PR.

**7. The user creates and merges the PR manually.**

**8. On the user's go-ahead, return to step 1** for the next change.

---

## Hard rules

| Rule | Why |
|------|-----|
| Cut every branch from `main` | A branch cut from another branch is a stacked PR |
| Never start change N+1 before N is merged | Same reason; only one branch in flight |
| One commit per branch | The PR is the review unit; a merged PR is one commit on `main` |
| Never push to `main` | `main` only advances through merged PRs |
| Never run `gh pr create` / `gh pr merge` | Opening and merging PRs is the user's call |

## Verify the merge before continuing

`main` moving is the only proof step 7 happened. A squash merge rewrites the
commit, so the local branch will not be an ancestor of `main` — check the
subject line, not the hash:

```bash
git fetch origin --prune
git log origin/main -1 --format='%h %s'
```

Then delete the stale local branch (`git branch -D <branch>`) and start the next
one. Do not assume a merge; if `main` has not moved, ask.

## Splitting work

Work too large for one commit is split into a **sequence** of PRs, not a stack.
Each does one thing, passes the gates on its own, and is merged before the next
begins. Order them so every PR leaves `main` green — a PR that needs a later PR
to build is in the wrong position.
