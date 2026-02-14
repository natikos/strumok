# Strumok

Electricity reporting system for a garden cooperative with a shared utility bill.

## Project scope

- Household user accounts and authentication
- Monthly meter reading submission
- Usage and payment tracking per household
- Cooperative reserve fund accounting

## Repository structure

- `backend/` — API, database models, and business logic
- `frontend/` — SPA client application
- `docker-compose.yml` — local PostgreSQL container

## Documentation

- Backend setup and run guide: [backend/README.md](backend/README.md)
- Frontend setup and run guide: [frontend/README.md](frontend/README.md)

## Local infrastructure

Start PostgreSQL from repo root:

```bash
docker compose up -d
```
