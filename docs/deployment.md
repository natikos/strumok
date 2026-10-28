# Deployment

## Platform

The app is deployed to [FastAPI Cloud](https://fastapicloud.com). FastAPI Cloud supports FastAPI backend deployments only — it does not host frontends separately.

## Frontend Strategy

The Vue.js frontend is served by FastAPI as static files. This means:

- The frontend is built (`bun run build` → `dist/`) and the output is mounted in FastAPI using `StaticFiles`
- A SPA fallback serves `index.html` for all non-API routes
- Both frontend and backend share the same origin, so no CORS configuration is needed and cookie-based auth works seamlessly
- Frontend updates require redeploying the backend

## Deployment Flow

Deployments are triggered automatically via GitHub Actions when a version tag is pushed:

```bash
git tag v1.2.3
git push origin v1.2.3
```

The workflow (`.github/workflows/deployment.yml`) will:

0. Run a `preflight` job that fails the workflow unless `ci.yml` succeeded on
   the tagged SHA. `deploy` `needs:` it, so nothing deploys on red or missing CI.
1. Build the frontend (`bun run build` inside `frontend/`)
2. Deploy the backend to FastAPI Cloud (`uv run fastapi deploy` inside `backend/`)

### Migrations

Apply migrations to production *before* tagging, since the app refuses to start
on an outdated schema:

```bash
pg_dump "$DATABASE_URL" -Fc -f pre-migration.dump   # always, first
cd backend && DATABASE_URL=... uv run alembic upgrade head
```

Migrations must be backward-compatible with the previously deployed code
(add first, remove in a later release). Automating this step in the release
workflow is a follow-up; it should run before the `deploy` job.

**One-time prod baseline:** `0000` was generated from the models, not from prod.
Diff a `pg_dump --schema-only` of prod against a fresh `alembic upgrade 0000`
schema, fix any drift in a new migration, then `alembic stamp 0000` in prod
(do not run `0000` there). `0001` adds a unique index on
`electricity_rates.effective_from` and fails if prod has duplicates.

You can also trigger a deployment manually from the GitHub Actions UI using the **workflow_dispatch** option.

### Required GitHub Secrets

| Secret                 | Description                  |
| ---------------------- | ---------------------------- |
| `FASTAPI_CLOUD_TOKEN`  | FastAPI Cloud deploy token   |
| `FASTAPI_CLOUD_APP_ID` | FastAPI Cloud app identifier |

## Backups

The database is backed up on day 6 and day 11 of each month by `.github/workflows/db-backup.yml`. Setup, restore, and
the quarterly drill are in [operations.md](operations.md#database-backups).

## Push Reminders

Deadline push reminders run on an in-process APScheduler
(`backend/app/api/push/scheduler.py`), started from the app's lifespan. It
fires the `opening` variant on day 1 and the `final` variant on day 5, at
06:00 UTC (Kyiv morning). The instance must be awake on those days; if it is
put to sleep after the 10th, wake it before the 1st. `send_reminders` is
idempotent per `(period, variant)`.

## Environment Variables

| Variable                 | Description                                                                       |
| ------------------------ | --------------------------------------------------------------------------------- |
| `DATABASE_URL`           | PostgreSQL connection string                                                      |
| `AUTH_SECRET_KEY`        | JWT signing secret                                                                |
| `AUTH_ALGORITHM`         | JWT algorithm (default: `HS256`)                                                  |
| `AUTH_ACCESS_TOKEN_EXPIRATION` | Access token lifetime in minutes (default: `60`); refreshed via `/auth/refresh` |
| `CORS_ORIGINS`           | Comma-separated list of allowed origins                                           |
| `ENVIRONMENT`            | **Required.** `development` or `production` — no default, startup fails otherwise |
| `BREVO_API_KEY`          | Brevo transactional email API key                                                 |
| `BREVO_SENDER_EMAIL`     | Verified Brevo sender address                                                     |
| `BREVO_APP_BASE_URL`     | Public app origin used to build verification links                                |
| `PUSH_VAPID_PUBLIC_KEY`  | VAPID public key for Web Push notifications                                       |
| `PUSH_VAPID_PRIVATE_KEY` | VAPID private key for Web Push notifications                                      |
| `PUSH_VAPID_SUBJECT`     | Contact URI (`mailto:` or URL) sent with Web Push requests                        |
