# Metrics

```bash
python3 scripts/project_metrics.py              # rework, convention, open issues
python3 scripts/project_metrics.py --coverage   # also runs the frontend suite (slow)
python3 scripts/project_metrics.py --since 2026-08-01
```

Read-only. It shells out to `git` and `gh` and prints a report; it writes
nothing and needs no setup beyond an authenticated `gh`.

## What is measured, and what deliberately isn't

The question that prompted this was whether the agentic setup is efficient.
That question is not answerable from what this repo records, for three reasons
worth writing down so it isn't re-litigated:

- **No counterfactual.** The project has been agentic since its first commit.
  A lead time of four minutes cannot be evidence the framework works, because
  there is no non-agentic version of this project to compare it against.
- **One developer, few issues.** Any cycle-time or throughput number is
  dominated by which task happened to be picked that day. Test infrastructure
  and a one-line commit-message tweak differ by an order of magnitude for
  reasons unrelated to how the work was done.
- **Issue timestamps are ceremony.** `commit-work` files an issue and closes it
  within the same flow, often minutes apart. Lead time computed from those
  timestamps measures the skill's latency, not the work.

So there is no cycle time, throughput, or velocity here. What survives without
a baseline is **rework**: did a change need fixing shortly after it landed.

## The metrics

### Rework

Two independent signals, because each is weak alone:

1. **Fix-follows-change.** A `fix(...)` commit landing within 14 days of a
   `feat(...)`/`refactor(...)` in the same scope *and touching at least one of
   the same files*. The file-overlap requirement matters: on this repo's
   history, scope alone paired a deadline-calculation rename with an unrelated
   commit adding OpenAPI examples, purely because both were `meter-readings`.
2. **File churn.** Files re-touched within 14 days, regardless of commit type.
   Catches unsettled work that was never labelled as a fix.

Neither is a verdict. A file at the top of the churn list may be under active
development rather than badly built — `en.json`/`ua.json` move whenever any
user-facing string changes, and that is normal. Treat the list as a place to
look, not a score.

**Repeated subjects** are called out separately. Two commits with an identical
subject usually means a change was redone rather than extended.

### Commit convention compliance

Checks subjects against [contributing.md](contributing.md): Conventional
Commits format, a scope, an issue number, and the 65-character budget.

Two scoping rules keep this honest:

- Only commits from **2026-08-06** onward are checked — the date
  `contributing.md` landed. Earlier commits predate the rules, and reporting
  them as violations would describe project history, not a problem.
- Subject length **excludes the PR number that squash-merge appends**. The
  budget governs what you write; the merge adds the rest.

### Open issues

Count and age of open issues, with anything labelled `bug`/`defect` marked and
the oldest defect age called out.

### Coverage

Frontend only, via `@vitest/coverage-v8`. The backend has no `pytest-cov`
dependency, so it reports as unavailable rather than this script adding a
dependency as a side effect. To enable it, add `pytest-cov` to the `dev` extra
in `backend/pyproject.toml`.

Off by default because it runs the full suite.

## Not included: per-specialist attribution

The most interesting question — which specialist (`tech-lead`, `qa-automation`,
…) earns its cost, and what an issue costs in tokens — is **not** answerable
from git or `gh`. Neither records which subagent ran or what it spent.

Capturing it means a hook writing agent invocations and token counts to a local
log, which only accumulates data going forward and would show nothing useful
for weeks. That is worth building only if the rework numbers above show a
problem worth explaining. Building attribution before knowing there is
something to attribute is how dashboards end up unread.
