---
description: Draft and file a GitHub issue for a bug or task
allowed-tools: Bash(gh issue create:*), Bash(gh issue list:*), Bash(gh label list:*)
---

File a GitHub issue for: $ARGUMENTS

If `$ARGUMENTS` is empty, use what was already discussed in this session as the
subject — do not ask the user to repeat it.

## 1. Classify

**Bug** if something already built behaves wrong. **Task** if it's new work,
a refactor, or a chore. If it's genuinely both, file the bug.

## 2. Draft

Title: one line, imperative, specific. No type prefix (`bug:` / `feat:`) — the
label carries that.

Body, 3–4 lines:
- **Summary** — what is happening or what needs doing, and why it matters.
- For a bug: **Steps to reproduce** → **Expected** → **Actual**.
  For a task: **Acceptance criteria** — 2–3 checkable bullets.
- **Area** — `backend`, `frontend`, `db`, `ci`, or a path like
  `backend/app/api/meter_readings`.

**Invent nothing.** Only facts from `$ARGUMENTS`, the session, or files you have
actually read. Anything you don't know — the exact version, the trigger, the
error text — is written literally as `Unknown — needs investigation`. A short
issue with honest gaps beats a plausible fabrication.

## 3. Pick a label

Run `gh label list`. Use `bug` for bugs and `enhancement` for tasks if they
exist; otherwise pick the closest existing label, or none. Never create a label.

Applying a label needs write access on the repo. If `--label` is rejected, file
the issue without it and tell the user which label to add by hand — and that
`gh auth switch --user natikos` fixes it for next time.

Optionally run `gh issue list --search "<key words>"` to catch an obvious
duplicate — if you find one, say so and stop rather than filing again.

## 4. Show the draft, then file

Print the title, body, and label to the user **before** filing. Then file it:

```
gh issue create --title "<title>" --body "<body>" --label "<label>"
```

Report the returned issue URL.

## 5. If gh is not authenticated

The `gh` calls above will fail with an auth error. Do not retry and do not fail
quietly — print the formatted issue (title, body, label) so the user can paste
it into GitHub manually, and tell them to run `gh auth login` to file directly
next time.
