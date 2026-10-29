# Testing

## Running the tests

**Backend** — needs a local Postgres (`docker compose up -d` from the repo root):

```bash
cd backend
uv sync --extra dev   # once
uv run pytest
```

**Frontend**:

```bash
cd frontend
bun run test          # bun run test:watch during development
```

**End-to-end** (Playwright, Chromium at 360px) — needs the same local Postgres:

```bash
cd frontend
bunx playwright install chromium   # once
bun run e2e                        # builds, then runs the suite
bun run e2e:only                   # skip the build when backend/dist is current
```

All three run in CI (`.github/workflows/ci.yml`). The backend and e2e jobs get a
`postgres:17.6` service container; the frontend job pins `TZ=UTC` so date-sensitive
tests don't depend on the runner's timezone. The deploy preflight requires the
whole workflow to pass, so a red e2e run blocks a release. None of them run in the
pre-commit hooks.

### Postgres version

Local (`docker-compose.yml`) and CI are both pinned to **17.6**, the production
patch version. Keep all three in step — testing against a different version than
production is how version-specific behaviour slips through. When production is
upgraded, bump both pins in the same change.

Changing the **major** version means recreating the volume, since a data directory
written by an older major refuses to start under a newer one (`FATAL: database
files are incompatible with server`). This destroys local data — dump anything worth
keeping first:

```bash
docker compose down -v && docker compose up -d
```

## Strategy

Integration-first on the backend, unit tests for frontend logic, and a small
Playwright suite for the journeys a resident or the head walks through end to end.

The backend services are thin wrappers around SQL — `get_owned_household_id` is one
`select` with two `where`s, and `PeriodAlreadySubmittedError` exists only because
Postgres raises on the `uq_household_period` constraint. Unit tests with a mocked
session would assert the mocks rather than the behaviour that matters, so tests go
through the real app via `TestClient`, against a real database, with real auth.

## Backend

### Test database

Each run creates a throwaway `strumok_test_<random>` database on the local Postgres
server and drops it at the end. Point it somewhere other than the default with
`TEST_DATABASE_URL`; a guard in `conftest.py` refuses any non-local host, because
`backend/.env` holds real development credentials that pydantic-settings would
otherwise pick up.

**Postgres is required — SQLite will not do.** `NUMERIC` columns come back as floats
under SQLite, which destroys the exact-`Decimal` guarantee that money handling
depends on, and the import script uses Postgres-only features
(`on_conflict_do_update`, `LAG() OVER (...)`).

### Isolation

Each test runs inside a transaction that is rolled back at teardown, so tests never
see each other's rows and the schema is created only once per session.

This is slightly more involved than usual because the service layer commits its own
transactions — `submit_meter_reading` calls `session.commit()`, and
`session.rollback()` when the unique constraint fires. The session is therefore
bound to an external transaction in `join_transaction_mode="create_savepoint"`, and
an `after_transaction_end` listener opens a fresh SAVEPOINT whenever the service
ends one. The service's `commit()` releases a savepoint rather than the real
transaction, and the outer transaction is rolled back wholesale afterwards.

The failure mode here is silent: a subtly wrong fixture lets rows leak while every
test still passes, showing up much later as order-dependent flakiness. So
`tests/test_harness.py` tests the harness itself — one test writes rows, the next
asserts an empty database, once through the ORM and once through the API so the
service's own commit is covered. **Keep those tests.** If you change the `session`
fixture, verify they still fail when isolation is broken (swap the teardown
`rollback()` for a `commit()` and confirm the suite goes red).

### Writing a test

`tests/factories.py` builds rows; each factory flushes rather than commits, so
records get primary keys while staying inside the rolled-back transaction.

```python
from tests.factories import authenticate, make_household, make_user

def test_cannot_read_another_households_readings(client, session):
    owner = make_user(session, email="owner@example.com")
    other = make_user(session, email="other@example.com")
    household = make_household(session, user_id=owner.id)
    authenticate(client, other)

    response = client.get("/meter-readings", params={"household_id": household.id})

    assert response.status_code == 403
    assert response.json()["detail"] == "householdNotAccessible"
```

### Mocking boundaries

- **Real database.** Never mock `Session` — the constraint, the `NUMERIC` round-trip
  and the `ORDER BY` are the point.
- **Real auth.** `get_current_user` is deliberately *not* overridden. Household
  scoping is the boundary most worth testing, and stubbing auth would mock away the
  thing under test. Use `authenticate(client, user)` for a real signed cookie, or
  `POST /auth/login` to exercise the password path too.
- Only `get_session` is overridden, to hand back the rolled-back session.
- bcrypt is intentionally slow; `make_user` reuses one cached hash. Pass an explicit
  `password=` only when a test needs a distinct one.

Note `ENVIRONMENT` is pinned to `development` in `conftest.py`. Anything else makes
`settings.auth_cookie_secure` true, and a `Secure` cookie is never returned over the
test client's plain-http transport, which breaks every authenticated request.

## Frontend

`vitest.config.ts` is separate from `vite.config.ts` so tests don't pull in the PWA
plugin or the PrimeVue auto-import resolver. **Because the resolver is absent,
PrimeVue components are not registered globally in tests** — register the ones a
component needs via `global.components`, or stub them.

`vitest.setup.ts` restores timers and mocks and clears storage after each test.

`src/shared/testing/mount.ts` provides `mountWithPlugins` (i18n + PrimeVue
configured as the app configures them) and `appPlugins()` for specs that want to
call `mount` directly and keep full prop type inference. Each mount gets a fresh
i18n instance — the app-level singleton reads the stored language at import time,
so sharing it leaks locale state between tests.

Mock the network at `fetch`, not at `openapi-fetch`, and never hand-edit
`src/shared/api/generated/openapi.ts`.

Coverage (`bunx vitest run --coverage`) is a local diagnostic; CI does not gate on a
percentage.

## End-to-end (e2e)

Playwright drives Chromium against the real stack: the frontend built into
`backend/dist`, served by uvicorn on `127.0.0.1:8787`, with `ENVIRONMENT=e2e` and a
throwaway `strumok_e2e` database. Same origin, real cookie auth, real CSRF.

**When to write one.** Only for what the other suites structurally can't see: a
flow across several screens, frontend and backend together, network conditions
(offline, an expired session), the service worker, or the 360px layout. Billing
rules, validation and scoping belong in pytest; component logic in Vitest. Keep
the suite to the journeys that matter — each one costs CI time and upkeep.

**Layout.** Specs are `frontend/e2e/*.spec.ts` (outside `src/`, so Vitest never
picks them up), type-checked by `bunx tsc -p e2e --noEmit`. `frontend/e2e/fixtures.ts`
extends Playwright's `test` with the helpers below; seed helpers live in
`frontend/e2e/support/`. `frontend/playwright.config.ts` holds the server command
and its environment.

**The server.** Playwright's `webServer` runs `backend/scripts/e2e_prepare_db.py`
(drop, recreate, `alembic upgrade head` — migrations, not `create_all`, so a missing
migration fails the suite) and then uvicorn. Every setting is passed explicitly in
the config, so `backend/.env` can never fill a gap; override the database with
`E2E_DATABASE_URL`. It never reuses a running server.

**`ENVIRONMENT=e2e`.** The backend refuses to start in this mode unless the database
is on localhost/127.0.0.1 and its name ends in `_e2e`, and IMAP is unset — so it can
never run against production. In this mode only:

- the test-only router `/__e2e` is mounted (absent from `/openapi.json`):
  `POST /reset`, `PUT|DELETE /clock`, `POST /users`, `GET /outbox`;
- `send_email` appends to an in-memory outbox instead of calling Brevo;
- the reminder/inbox scheduler doesn't start (its jobs would fire mid-test);
- a schema behind head fails startup, as in production.

**Isolation.** One database per run; before every test the fixture calls
`POST /__e2e/reset`, which truncates every table with `RESTART IDENTITY` (so ids and
`STR-<id>` references are predictable) and clears the outbox and clock. One worker:
the clock, outbox and database are server-wide.

**Time.** Billing follows Kyiv time on both sides, so a test that cares about the
date calls `setNow(iso)` before its first `page.goto`. It sets the backend clock
(`PUT /__e2e/clock`, an offset in `app.core.time` that `utc_now` and `kyiv_now` read)
and the browser clock (`page.clock.install`). Both keep running at real speed —
never set only one side, and never `setFixedTime`. JWT expiry is checked against
the same app clock, so moving it forward expires a session. Pin noon Kyiv on an
absolute date, away from midnight and the late-March and late-October DST changes.

**Seeding.** `POST /__e2e/users` creates an active, verified user (the only way to
get the first admin, since sign-up is closed). Everything else — households, rates,
invites, readings, ownership — goes through the real admin and resident API with
`X-Requested-With: XMLHttpRequest`. Invite and reset links are read from the
outbox. Log in with `page.request.post("/auth/login")` unless the test is about
logging in. If an API path is impractical, add an `/__e2e` endpoint that calls the
service layer; never write raw SQL from a spec.

**Rules.** Don't mock the backend with `page.route` (offline simulation is the
exception). Use role and label selectors with web-first assertions, never
`waitForTimeout`. Seed users in English and don't assert Ukrainian text unless the
test is about i18n. Service workers are blocked by default; a spec that needs one
opts in with `test.use({ serviceWorkers: "allow" })`. A known, tracked defect is
pinned with `test.fail` (Playwright) or `pytest.mark.xfail(strict=True)` and a
comment naming the issue; the mark comes off in the fix's PR. Never run `bun run api:types`
against the e2e server. On a CI failure, download the `playwright-report` artifact
and open the trace.

## Not yet covered

The harness is in place but real coverage is thin — currently only the harness's own
tests. Highest-value gaps, roughly in order:

1. **Household scoping.** `require_household_id` takes `household_id` from the query
   string and is safe only because ownership is re-checked; nothing stops a future
   route skipping that dependency. Also worth pinning: with the parameter omitted, a
   user owning several households resolves to the oldest one.
2. **Usage maths.** The service clamps negative usage and takes the previous reading
   as the latest one before the submitted period; both behaviours still want pinning
   in tests.
3. **Duplicate periods**, including the concurrent case that the unique constraint
   catches.
4. **`shared/api/client.ts` refresh path** — single in-flight refresh, one retry, no
   recursion.
5. **Dashboard composables** (`useMeterReadings`), which reimplement deadline maths
   that `deadline.ts` already gets right.
