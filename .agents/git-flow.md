<!-- agentcfg:start -->
<!-- core/git-flow.md · v0.18.0 -->
# Git flow

The branch → commit → PR loop for **every** change in this repository. There is
one flow; it applies to tooling, docs, config and crates alike. Read it
before the other rules — everything else fits inside it.

The defining constraint: **no stacked PRs.** Each branch is cut from an
up-to-date `main` and is merged before the next one is cut. Only one branch is
ever in flight.

---

## The loop

```bash
# 1. Start from an up-to-date main
git switch main
git pull --ff-only

# 2. Cut the branch (format: see Branch naming)
git switch -c <type>/<short-description>

# 3. Make the change, then run the gates
just ci                              # all four gates; see Testing instructions

# 4. One commit (format: see Commit message guidelines)
git add <the files this change touches>
git commit

# 5. Push
git push -u origin <type>/<short-description>
```

**6. Output the PR title and description, then STOP.**

Use the template in *PR instructions*. Do not open the PR.

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

A push to `main` is not only a process violation here. `bump-version.yml`
triggers on it, reads the commit subject, and pushes a release tag — so a
hand-pushed commit silently cuts a release.

The same mechanism makes two merge rules load-bearing:

- **Squash-merge every PR.** A merge commit's subject — `Merge pull request #12
  from …` — matches no commit type, so no release is cut while the workflow
  still reports success.
- **One commit per branch is a versioning rule, not a style.** Only the subject
  of the newest commit on `main` is read. A rebase merge of `feat: X` then
  `fix: Y` cuts a patch release, and the feature ships under a version that says
  nothing was added.

## Verify the merge before continuing

`main` moving is the only proof step 7 happened. A squash merge rewrites the
commit, so the local branch will not be an ancestor of `main` — check the
subject line, not the hash. Look past the newest commit: the squash appends
` (#N)` to the subject, and `bump-version.yml` may push a `chore: release`
commit on top of it.

```bash
git fetch origin --prune
git log origin/main -5 --format='%h %s'
```

Then delete the stale local branch (`git branch -D <branch>`) and start the next
one. Do not assume a merge; if `main` has not moved, ask.

`main` moving is not the same as the change having landed. A merge here starts
work the pull request never ran — the version bump, the tag, and whatever
watches for that tag — under different triggers and a different token, so a
green pull request says nothing about any of it. Where the merge triggered
something, check that it produced the right thing rather than that it went
green: a release with no assets, or notes describing the wrong range, is a
success as far as the workflow is concerned. What a merge sets off varies with
this repository's deployment, and its rules say which; where it sets off
nothing, there is nothing to check.

## Splitting work

Work too large for one commit is split into a **sequence** of PRs, not a stack.
Each does one thing, passes the gates on its own, and is merged before the next
begins. Order them so every PR leaves `main` green — a PR that needs a later PR
to build is in the wrong position.
<!-- agentcfg:end -->
