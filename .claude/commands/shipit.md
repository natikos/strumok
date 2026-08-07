---
description: Commit anything pending, gate locally, open a tracked PR, wait for green, squash-merge, and clean up
allowed-tools: Bash(git status:*), Bash(git branch:*), Bash(git switch:*), Bash(git add:*), Bash(git commit:*), Bash(git push:*), Bash(git pull:*), Bash(git fetch:*), Bash(git log:*), Bash(git diff:*), Bash(git remote:*), Bash(git rev-parse:*), Bash(gh repo view:*), Bash(gh api:*), Bash(gh issue create:*), Bash(gh issue list:*), Bash(gh issue view:*), Bash(gh label list:*), Bash(gh pr create:*), Bash(gh pr view:*), Bash(gh pr checks:*), Bash(gh pr merge:*), Bash(uv run ruff:*), Bash(uv run pytest:*), Bash(bunx eslint:*), Bash(bun run test:*), Bash(bun run build:*)
---

Land the current work: $ARGUMENTS

`$ARGUMENTS` is optional — it may carry a subject or an issue number. If empty,
derive everything from the branch, the diff, and this session.

Much of the setup may already be done: the `commit-work` skill creates the
branch, ensures the issue exists, and commits in slices during implementation.
Stages 1–3 **verify** that rather than redoing it, and fill in whatever is
missing.

Work through the stages in order. **Stop and report** at the first stage that
fails — never skip ahead, never paper over a failure. Stage 6 merges
automatically once CI is green; it does not wait for confirmation.

Deployment is a separate step, not part of this flow — stop after cleanup.

---

## 1. Preflight

Run these and read the answers before touching anything:

- `git status --porcelain` and `git branch --show-current`
- `gh api repos/:owner/:repo --jq .permissions.push`

**If `permissions.push` is not `true`**, the active `gh` account cannot merge
this PR. Stop immediately and tell the user:

> The active `gh` account lacks write access to `natikos/strumok`.
> Run `gh auth switch --user natikos`, then re-run `/shipit`.

Do not attempt the flow anyway, and do not switch accounts yourself — that
changes the user's global git tooling.

**Confirm there is something to ship.** If the tree is clean *and* the branch has
no commits ahead of `main`, there is nothing to land — say so and stop. If the
user asked to implement something that doesn't exist yet, this command is
premature: implement it first (per `CLAUDE.md`, committing via `commit-work`),
then run `/shipit`.

## 2. Branch

If already on a feature branch, keep it — `commit-work` most likely created it.

If on `main` with uncommitted changes, create one now:
`git switch -c <type>/<slug>`. Never commit directly to `main`.

## 3. Issue

Recover the issue number from the existing commit subjects first —
`git log main..HEAD --format=%s` — since `commit-work` suffixes each one with
`(#n)`. If `$ARGUMENTS` names a number, that wins.

If neither yields one, search: `gh issue list --search "<key words>" --state open`,
and reuse a relevant open issue. Otherwise file one with the `create-issue`
skill's rules: `bug` label if this fixes broken behaviour, `enhancement` if it's
new work; title imperative and specific; body is summary +
repro-or-acceptance-criteria + area; anything unknown written literally as
`Unknown — needs investigation`.

Hold on to the number — it's needed for the PR title and body.

## 4. Commit anything pending

If the tree is clean, skip this stage — `commit-work` already handled it.

Otherwise commit what's left per the Commit Messages section of
`docs/contributing.md` — stage deliberately, review `git diff --staged` for
debug leftovers and secrets, and write the message to that spec.

## 5. Gate locally, then open the PR

Run the same gates CI runs, so a red PR is caught before it's opened. Needs
Postgres up — `docker compose up -d` from the repo root.

```
cd backend  && uv run ruff check . && uv run pytest
cd frontend && bunx eslint . && bun run test && bun run build
```

Use `bunx eslint .`, not `bun run lint` — the latter auto-fixes and would leave
uncommitted edits. `bun run build` runs `vue-tsc --noEmit` first, so it is the
type gate too; it writes to the gitignored `backend/dist/` and won't dirty the
tree.

**If any gate fails, stop and report the output verbatim.** Do not open a PR.

Then `git push -u origin <branch>` and `gh pr create`.

PR title: the same subject format as a commit, per `docs/contributing.md`.
Since this squash-merges, the PR title becomes the commit subject on `main`.

PR body: 2–4 lines covering what changed and *why* — the squash-merge collapses
the branch's commits, so this body is what survives as the durable explanation.
Then `Closes #<issue>` on its own line. **No "Test plan" section.** No
`Co-Authored-By`. Print the PR URL.

## 6. Gate on green, then merge

Wait for checks: `gh pr checks --watch`.

`.github/workflows/ci.yml` runs on pull requests, covering backend lint + pytest
and frontend lint + test + build. If `gh pr checks` reports **no checks
configured**, CI did not trigger — treat that as **not green**, never as a pass,
and report it rather than merging on the strength of stage 5 alone.

If checks fail, stop and report which job failed with its output. Do not merge.

Once green, merge without waiting for confirmation:
`gh pr merge --squash --delete-branch`.

Squash keeps `main` linear at one commit per change, which makes `git blame`
land on a commit that explains the whole change. The branch's incremental
commits stay visible in the PR for review.

## 7. Clean up

```
git switch main
git pull --ff-only
git branch --delete <branch>     # if stage 6 left it behind
git fetch --prune
```

Verify with `git branch -a` that neither the local nor the remote branch remains,
and that `main` contains the squashed commit.

---

## Report

End with a compact summary: branch, commits, issue, PR, local gate results, CI
result, merge, and cleanup. State plainly anything you skipped and why.
Deployment is not part of this command — mention it's a separate step if the
user wants to ship to production.
