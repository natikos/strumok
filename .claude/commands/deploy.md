---
description: Tag and push a release to trigger the FastAPI Cloud deployment
allowed-tools: Bash(git status:*), Bash(git switch:*), Bash(git pull:*), Bash(git fetch:*), Bash(git log:*), Bash(git tag:*), Bash(git push origin v*), Bash(git describe:*), Bash(gh api:*), Bash(gh run list:*), Bash(gh run view:*), Bash(gh workflow run:*)
---

Deploy to production. Takes no arguments — the version is always derived from
the commits since the last tag.

Deployment is push-to-tag, per `docs/deployment.md`: pushing a `v*` tag fires
`.github/workflows/deployment.yml`, which builds the frontend and runs
`fastapi deploy` against FastAPI Cloud. There is no staging environment — a
pushed tag deploys straight to production.

---

## 1. Preflight

- `git status --porcelain` — the tree must be clean. If not, stop and tell the
  user to commit or stash first. This command never commits on your behalf.
- `git branch --show-current` — must be `main`. If not, stop: deploys are cut
  from `main` only.
- `git fetch --prune && git pull --ff-only` — make sure local `main` matches
  `origin/main`. If `pull --ff-only` fails, stop and report; don't force anything.
- `gh api repos/:owner/:repo --jq .permissions.push` — if not `true`, stop and
  tell the user the active `gh` account can't push tags here.

## 2. Determine the version

- `git tag --list 'v*' --sort=-v:refname | head -1` for the latest tag.

If no tag exists yet, this is the first release — start at `v0.1.0`.

- `git log <latest-tag>..HEAD --format='%s%n%b'` to see every commit shipping
  in this release, subject and body.

Major stays pinned at `0` — the project isn't at a stable/real release yet
(billing is unimplemented, per `docs/known-limitations.md`). It only moves to
`1` when the user explicitly declares the v1.0 release; never infer that bump
from commits. Until then, classify only between minor and patch, from
Conventional Commits types (per `docs/contributing.md`):

- **minor** — at least one `feat` commit since the last tag.
- **patch** — everything else (`fix`, `chore`, `refactor`, `docs`, `test`,
  `style` only).

Compute the new version by bumping the appropriate segment of the latest tag
(e.g. latest `v1.4.2`, a `feat` present → `v1.5.0`; patch only → `v1.4.3`).

State the version you've picked and which commits drove the classification
before proceeding.

## 3. Confirm

This triggers a real production deploy. Show the user:
- the version to be tagged
- the commit it points to (`git log -1 --format='%h %s'`)
- the list of commit subjects since the last tag (what's shipping)

Then stop and wait for explicit confirmation before tagging and pushing.
Do not proceed on an ambiguous or implied "yes."

## 4. Tag and push

```
git tag <version>
git push origin <version>
```

Never use `--force` on a tag push. If the tag already exists remotely, stop and
report the conflict rather than overwriting it.

## 5. Watch the deployment

```
gh run list --workflow=deployment.yml --limit 1
gh run view <run-id>
```

Poll until the run completes. If it fails, report the failing step's output
verbatim — do not retry or re-push the tag yourself; that's the user's call
(a fixed re-deploy needs a new version, since tags are immutable here).

## Report

End with a compact summary: version tagged, commit it points to, workflow run
URL, and final status (success/failure). If it failed, name the failing step
and stop — don't suggest a fix and apply it in the same breath without asking.
