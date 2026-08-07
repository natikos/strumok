# Contributing

## Git Hooks

Pre-commit hooks (lint + format on staged files) run via [lefthook](https://github.com/evilmartians/lefthook). One-time setup per clone:

```bash
brew install lefthook   # or see lefthook docs for other package managers
lefthook install
```

## Tests

```bash
docker compose up -d              # backend tests need a local Postgres
cd backend  && uv run pytest
cd frontend && bun run test
```

Both suites run in CI. Pre-commit hooks deliberately don't run them — the backend
suite needs a database, which a hook can't assume. See [testing.md](testing.md) for
the harness, fixtures, and what still needs coverage.

## Commit Messages

This section is the single source of truth for commit conventions — the
`commit-work` skill and the `/shipit` command both defer to it rather than
restating the rules.

### Subject

All commit messages follow the [Conventional Commits](https://www.conventionalcommits.org/)
specification, with the issue number suffixed:

```
<type>(<scope>): <description> (#<issue>)
```

- **Type**: `feat`, `fix`, `chore`, `refactor`, `docs`, `test`, `style`.
- **Scope**: the area — `auth`, `meter-readings`, `households`, `frontend`,
  `backend`, `ci`, `db`.
- **Description**: imperative and specific. Never generic — no "update",
  "changes", "fixes".
- **Issue**: the tracked issue this belongs to. Omit the suffix only when the
  work genuinely isn't tracked, and say so when reporting.

Keep the whole subject **under 65 characters**. Squash-merging appends the PR
number, so a subject at the limit still lands near 70 in `git log --oneline`.
When it doesn't fit, shorten the description — don't drop the type, scope, or
issue number, which carry more signal per character than any description word.
Detail belongs in the body.

Examples:

- `feat(auth): add JWT authentication (#14)`
- `fix(meter-readings): correct period validation (#31)`

### Body

The subject says *what* changed. **If the why isn't obvious from the subject,
add a body** — one short paragraph, wrapped at 72 characters, explaining the
reasoning: what was wrong before, what forced this approach, what was ruled out.

Write for someone running `git blame` on the line in a year with no memory of
the discussion. The diff already shows what changed. What it can't recover is
why.

```
fix(meter-readings): reject readings below prior period (#31)

A resident submitting a meter value lower than last month's silently
produced negative usage, which flowed into the shared-bill total and
made every other household's share wrong.

Validating in the service rather than the schema because the check
needs the prior period, which the request body doesn't carry.
```

Skip the body when the subject genuinely covers it — `chore(deps): bump ruff to
0.14.2 (#40)` needs nothing more. Don't pad a trivial commit with invented
rationale, and don't guess at a constraint you don't understand.

### Trailers

Do not add a `Co-Authored-By` trailer.

### Granularity

Commit each coherent slice — one behaviour added, one bug fixed, one refactor
completed — rather than once at the end. A good slice leaves the branch in a
state you could explain in one sentence. Stage deliberately (`git add` the files
for *this* slice, never `-A`) and read `git diff --staged` before committing.

Branch commits are squashed on merge, so `main` keeps one commit per change.
The incremental commits are the reviewable unit while the PR is open.
