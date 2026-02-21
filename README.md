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

- Backend setup and run guide: [backend/README.md](backend/README.md)
- Frontend setup and run guide: [frontend/README.md](frontend/README.md)

## API contract

- Backend errors use `HTTPException.detail` as a stable camelCase error code (for example: `invalidCredentials`, `emailAlreadyRegistered`), not user-facing text.
- Frontend API contract/types are generated automatically from OpenAPI (`frontend/src/shared/api/generated/openapi.ts`) and should be treated as the source of truth for request/response typing.

## Local infrastructure

Start PostgreSQL from repo root:

```bash
docker compose up -d
```
