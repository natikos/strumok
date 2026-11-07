# Local development

Everything needed to run Strumok on your machine. Commands run from the repo
root unless a `cd` says otherwise.

## First-time setup

```bash
docker compose up -d                          # Postgres 17 on localhost:5432
cp backend/.env.example backend/.env          # defaults already point at the compose DB
cd backend && uv sync --extra dev             # Python 3.14+, see backend/README.md
uv run alembic upgrade head                   # create the schema (see Migrations)
cd ../frontend && bun install
```

## Run

| What | Command |
| ---- | ------- |
| Backend (auto-reload) | `cd backend && uv run uvicorn app.main:app --reload` → http://localhost:8000 (`/docs` for Swagger) |
| Frontend (Vite dev server) | `cd frontend && bun run dev` → http://localhost:5173 |
| Frontend types from OpenAPI | `cd frontend && bun run api:types` (backend must be running) |
| Lint | `cd backend && uv run ruff check .` / `cd frontend && bun run lint` |
| Tests | see [testing.md](testing.md) |

In `development`, a database behind the newest migration only logs
`schemaOutdated`; in `production` and `e2e` the app refuses to start.

## Migrations

Alembic, in `backend/alembic/versions/`. It uses `DATABASE_URL` from
`backend/.env`, so run everything from `backend/`.

```bash
cd backend

uv run alembic upgrade head          # apply all pending migrations
uv run alembic current               # revision the DB is at
uv run alembic history --verbose     # all revisions
uv run alembic check                 # fails if models drifted from migrations (CI runs this)
```

**Changing a model:**

```bash
uv run alembic revision --autogenerate -m <name> --rev-id <NNNN>   # next free number
# review the generated file by hand, then:
uv run alembic upgrade head
```

Rules (details in [deployment.md](deployment.md#migrations)):

- Never edit a migration that has been applied anywhere else; add a new one.
- Keep them backward-compatible (add first, remove in a later release). A
  migration that drops, renames or alters something needs a
  `# contract: <why>` comment or `test_migration_safety.py` fails.
- Don't run migrations against production by hand: the release workflow does.

**Starting over locally:** `docker compose down -v && docker compose up -d`
wipes the database volume; then `uv run alembic upgrade head`.

**Downgrading** (`uv run alembic downgrade -1`) is fine on your own database,
but many downgrades drop ledger tables or columns, and `0013` cannot be undone.

## Data scripts

In `backend/scripts/` (run with `uv run python scripts/<name>.py`):
`import_meter_history.py`, `import_opening_balances.py`,
`set_balance_cutover.py` (spreadsheet imports), `check_migrations.py` (read-only revision check used by the release
workflow). `e2e_prepare_db.py` belongs to the Playwright harness.

## Git hooks

One-time `lefthook install`, see [contributing.md](contributing.md#git-hooks).
