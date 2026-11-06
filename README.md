# Strumok

Electricity reporting system for a garden cooperative with a shared utility bill.

## Business context

In our neighborhood cooperative, all households are covered by one shared electricity bill.  
Today, the process is mostly manual:

- Residents send meter readings in a messenger chat
- The cooperative head manually collects and verifies readings
- Payment amounts are calculated manually per household
- Final totals and balances are tracked in spreadsheets/messages

This approach is slow, error-prone, and hard to audit.

## Product goal

Strumok is a web app that digitizes this workflow end-to-end:

- Residents submit meter readings directly in the app
- The system automatically calculates each household's required payment
- Usage and payment history are stored in one place
- Cooperative leadership gets transparent, consistent accounting data

Primary outcome: reduce manual operations and provide clear, trustworthy billing for all cooperative members.

## Project scope

- Household user accounts and authentication
- Monthly meter reading submission
- Usage and payment tracking per household
- Cooperative reserve fund accounting

## Documentation

Start with the task-based index: **[docs/README.md](docs/README.md)**.

## Quick start

```bash
docker compose up -d                       # local Postgres
cp backend/.env.example backend/.env
cd backend && uv sync --extra dev && uv run alembic upgrade head
uv run uvicorn app.main:app --reload       # API on :8000
cd ../frontend && bun install && bun run dev   # app on :5173
```

Details, migrations and tests: [docs/development.md](docs/development.md).

## API contract

- Backend errors use `HTTPException.detail` as a stable camelCase error code (for example `invalidCredentials`, `emailAlreadyRegistered`), not user-facing text.
- Frontend API types are generated from the backend's OpenAPI schema (`frontend/src/shared/api/generated/openapi.ts`, via `bun run api:types`) and are the source of truth for request/response typing. Never edit that file by hand.
