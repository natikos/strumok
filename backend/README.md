# Backend

FastAPI + SQLModel + PostgreSQL. Run every command below from `backend/`.
Full local setup (database, migrations, frontend): [docs/development.md](../docs/development.md).

## Setup

Requires Python 3.14+ and [`uv`](https://docs.astral.sh/uv/) installed at user/system level (not inside the project venv).

```bash
cp .env.example .env        # then adjust values; defaults match docker-compose Postgres
uv sync --extra dev         # creates .venv and installs dependencies
uv run alembic upgrade head # create/upgrade the database schema
```

`uv run <cmd>` uses the project venv automatically; activating it
(`source .venv/bin/activate`) is optional.

## Run

```bash
uv run uvicorn app.main:app --reload    # development, auto-reload
python -m app.main                      # production-style, no reload
```

API: `http://localhost:8000`. Swagger UI at `/docs`, ReDoc at `/redoc`.

## Common commands

| Task | Command |
| ---- | ------- |
| Tests (needs `docker compose up -d`) | `uv run pytest` |
| Lint | `uv run ruff check .` |
| Apply migrations | `uv run alembic upgrade head` |
| New migration | `uv run alembic revision --autogenerate -m <name> --rev-id <NNNN>` |

More on migrations in [docs/development.md](../docs/development.md#migrations); on tests in [docs/testing.md](../docs/testing.md).

## Python version

Install 3.14 with [pyenv](https://github.com/pyenv/pyenv) (`pyenv install`, reads the version from the repo) or from [python.org](https://www.python.org/downloads/). Check with `python --version`.

## Troubleshooting

- **Wrong Python version:** see above; `uv` picks the interpreter from `pyproject.toml`.
- **`uv` not found:** `curl -LsSf https://astral.sh/uv/install.sh | sh` or `pip install uv`.
- **Module not found:** run `uv sync --extra dev` again and use `uv run`.
- **`schemaOutdated` in the log:** the database is behind the newest migration; run `uv run alembic upgrade head`.
