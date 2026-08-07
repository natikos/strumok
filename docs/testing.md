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

Both run in CI (`.github/workflows/ci.yml`). The backend job gets a `postgres:17.6`
service container; the frontend job pins `TZ=UTC` so date-sensitive tests don't
depend on the runner's timezone.

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

Integration-first on the backend, unit-only on the frontend, no e2e for now.

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
depends on, and the import script and migrations use Postgres-only features
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

## Not yet covered

The harness is in place but real coverage is thin — currently only the harness's own
tests. Highest-value gaps, roughly in order:

1. **Household scoping.** `require_household_id` takes `household_id` from the query
   string and is safe only because ownership is re-checked; nothing stops a future
   route skipping that dependency. Also worth pinning: with the parameter omitted, a
   user owning several households resolves to the oldest one.
2. **Usage maths.** Three implementations disagree — `app/api/meter_readings/service.py`
   does not clamp negative usage, while `migrations/001_calculate_meter_usage.sql`
   (`GREATEST(..., 0)`) and `scripts/calculate_meter_usage.py` (`max(..., 0)`) both do.
   The service also picks the "previous" reading by `ORDER BY period DESC`, i.e. the
   lexicographically greatest period rather than the one immediately before, so
   backfilling an older period computes usage against a newer reading.
3. **Duplicate periods**, including the concurrent case that the unique constraint
   catches.
4. **`shared/api/client.ts` refresh path** — single in-flight refresh, one retry, no
   recursion.
5. **Dashboard composables** (`useMeterReadings`), which reimplement deadline maths
   that `deadline.ts` already gets right.
