---
description: Branch, commit, open a tracked PR, gate on CI, merge, and clean up
allowed-tools: Bash(git status:*), Bash(git branch:*), Bash(git switch:*), Bash(git checkout:*), Bash(git add:*), Bash(git commit:*), Bash(git push:*), Bash(git pull:*), Bash(git fetch:*), Bash(git log:*), Bash(git diff:*), Bash(git remote:*), Bash(git rev-parse:*), Bash(gh repo view:*), Bash(gh api:*), Bash(gh issue create:*), Bash(gh issue list:*), Bash(gh issue view:*), Bash(gh label list:*), Bash(gh pr create:*), Bash(gh pr view:*), Bash(gh pr checks:*), Bash(gh pr merge:*), Bash(uv run ruff:*), Bash(bunx eslint:*), Bash(bun run build:*)
---

Ship the current work end to end: $ARGUMENTS

`$ARGUMENTS` is optional. It may carry a subject for the commit/issue. If empty,
derive everything from the diff and this session.

Work through the stages in order. **Stop and report** at the first stage that
fails — never skip ahead, never paper over a failure. Stage 7 requires
explicit user confirmation; do not pass it unattended.

Deployment is a separate step, not part of this flow — stop after merge and
cleanup.

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

Also confirm there is something to ship. If the tree is clean *and* the current
branch has no commits ahead of `main`, say so and stop.

## 2. Branch

- If on `main`: create a branch from current `main` — `git switch -c <type>/<slug>`,
  where `<type>` matches the Conventional Commits type (`feat`, `fix`, `chore`,
  `refactor`, `docs`) and `<slug>` is 2–4 kebab-case words from the change.
- If already on a feature branch: keep it. Do not re-branch.
- Never commit directly to `main`.

## 3. Issue

Check whether one already exists: `gh issue list --search "<key words>" --state open`.
If a relevant issue is already open, reuse its number and skip creation.

Otherwise create one — same rules as `/create-issue`: `bug` label if this fixes
broken behaviour, `enhancement` if it's new work; title imperative and specific;
body is summary + repro-or-acceptance-criteria + area; anything unknown written
literally as `Unknown — needs investigation`.

Hold on to the issue number — it's needed for the commit message, the PR title,
and the PR body.

## 4. Commit

Stage deliberately — `git add` the files belonging to this change, not `-A`.
Review `git diff --staged` before committing: look for debug leftovers, typos,
committed secrets, and stray `.env`/CSV files.

One Conventional Commits message per `docs/contributing.md`, with the issue
number suffixed:
`<type>(<scope>): <description> (#<issue>)`. Scope is the area (`auth`,
`meter-readings`, `frontend`, `ci`). **Do not add a `Co-Authored-By` trailer.**

If the branch already has the right commits, skip this stage.

## 5. Push and open the PR

`git push -u origin <branch>`, then `gh pr create`.

PR title: same convention as the commit, suffixed with the issue number —
`<type>(<scope>): <description> (#<issue>)`.

PR body: 2–4 lines of what changed and why, then `Closes #<issue>` on its own
line so the merge closes the issue. **No "Test plan" section.** No
`Co-Authored-By`. Print the PR URL.

## 6. Gate on green

Wait for checks: `gh pr checks --watch`.

**This repo currently has no CI workflow** — `.github/workflows/deployment.yml`
only fires on `v*` tags, so a PR has zero checks and `gh pr checks` will report
none. Treat "no checks configured" as **not green**, never as a pass. Fall back
to running the equivalent gates locally, and label them as such in your report:

```
cd backend  && uv run ruff check .
cd frontend && bunx eslint . && bun run build
```

(`bun run build` runs `vue-tsc --noEmit` first, so it is the type gate too. It
writes to the gitignored `backend/dist/`, so it will not dirty the tree. Use
`bunx eslint .` — not `bun run lint`, which auto-fixes and would leave
uncommitted edits.)

If any gate fails, stop and report the output verbatim. Do not merge.

## 7. Confirm, then merge

Show the user: PR URL, the gate result (real CI vs. local proxy), and the issue
it closes. **Ask for explicit confirmation to merge.**

On approval: `gh pr merge --squash --delete-branch`.

Squash keeps `main` linear and matches the one-commit-per-change history here.
`--delete-branch` removes the remote branch and the local one.

## 8. Clean up

```
git switch main
git pull --ff-only
git branch --delete <branch>     # if step 7 left it behind
git fetch --prune
```

Verify with `git branch -a` that neither the local nor the remote branch remains,
and that `main` contains the squashed commit.

---

## Report

End with a compact summary: branch, commit, issue, PR, how the change was gated
(real CI or local proxy), merge result, and cleanup. State plainly anything you
skipped and why. Deployment is not part of this command — mention it's a
separate step if the user wants to ship to production.
