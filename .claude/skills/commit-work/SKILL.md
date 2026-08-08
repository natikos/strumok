---
name: commit-work
description: Set up a work branch and commit in small, meaningful increments while implementing. Use at the START of any non-trivial piece of work (a feature, a multi-file fix, an issue you were asked to implement), and again each time a coherent slice is finished. Handles branch creation, ensuring a tracked issue exists, and writing commit messages that explain why. Does not push, open PRs, or merge — use the /shipit command for that.
---

Prepare the workspace for a piece of work, then commit it in slices as it lands.

This is the *during-the-work* half of shipping. It never pushes, never opens a
PR, never merges, never touches `main`. When the work is complete and ready to
land, the user runs `/shipit`.

## 1. Ensure a branch

Run `git branch --show-current`.

- **On a feature branch already** — keep it. Do not re-branch mid-work.
- **On `main`** — create one before the first commit:
  `git switch -c <type>/<slug>`, where `<type>` is the Conventional Commits type
  (`feat`, `fix`, `chore`, `refactor`, `docs`) and `<slug>` is 2–4 kebab-case
  words describing the change.

Never commit directly to `main`.

## 2. Ensure a tracked issue

Every branch needs an issue number — commits reference it, and `/shipit` reuses
it for the PR.

- **The request named one** ("implement X, issue #12") — use it. Confirm it's
  real with `gh issue view <n>`, but don't re-search.
- **No number given** — search first:
  `gh issue list --search "<key words>" --state open`. Reuse a relevant open
  issue if one exists.
- **Nothing found** — file one with the `create-issue` skill before the first
  commit.

If `gh` is unauthenticated or the search fails, don't block the work: proceed
without a number, commit without the `(#n)` suffix, and say plainly in your
report that the commits are untracked so `/shipit` can reconcile it later.

## 3. Commit each slice

**Follow the Commit Messages section of `docs/contributing.md`** — format,
body, trailers, and granularity are all defined there. Read it if it isn't
already in context. Do not restate or reinvent those rules here.

Two things that section calls for, applied to a long agent run:

- **Commit as you go.** A slice is coherent when it's one behaviour added, one
  bug fixed, one refactor completed, or a test file that passes. Don't wait for
  the whole task — these commits are the recovery points if the run goes wrong.
- **Read `git diff --staged` before every commit.** Beyond the usual review,
  watch for debug leftovers, stray `console.log`/`print`, commented-out code,
  committed secrets, and `.env` or CSV files. Fix them before committing.

**Get explicit approval before every commit.** When a slice is ready, stage
it, show the user `git diff --staged` and the drafted commit message, and wait
for their go-ahead before running `git commit`. Do not run `git commit` on
your own initiative — always ask first, for every commit, not just the first
one in a session. Exception: if the user has explicitly told you to run
hands-off for this task (e.g. "just commit as you go", `/shipit auto`), skip
the checkpoint for the commits that instruction covers — it's the approval
itself, given up front instead of per slice.

## 4. Report

After each commit, state in one line: the branch, the commit subject, and what's
still outstanding. When the work is done, say so and note that `/shipit` is the
next step — don't run it yourself unless the user asks.
