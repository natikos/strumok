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

1. Build the frontend (`bun run build` inside `frontend/`)
2. Deploy the backend to FastAPI Cloud (`uv run fastapi deploy` inside `backend/`)

You can also trigger a deployment manually from the GitHub Actions UI using the **workflow_dispatch** option.

### Required GitHub Secrets

| Secret                 | Description                                                                                    |
| ---------------------- | ---------------------------------------------------------------------------------------------- |
| `FASTAPI_CLOUD_TOKEN`  | FastAPI Cloud deploy token                                                                     |
| `FASTAPI_CLOUD_APP_ID` | FastAPI Cloud app identifier                                                                   |

## Push Reminders

The monthly meter-reading reminder runs in-process: an `AsyncIOScheduler`
started in the FastAPI app's lifespan (`backend/app/api/push/scheduler.py`)
fires the "opening" reminder on day 1 and the "final" reminder on day 5 of
each month, both at 08:00 UTC, calling the same `send_reminders` service the
`POST /internal/push/send-reminders` endpoint uses. That endpoint (secured by
`PUSH_REMINDER_SECRET`) still exists for manual re-triggering/testing.

Note: FastAPI Cloud's replica/restart behavior isn't verified here. If the
backend ever runs multiple replicas, each one's scheduler fires independently
and residents would get duplicate reminders — this hasn't been an issue with
a single replica but would need a DB-backed lock if that changes.


## Environment Variables

| Variable                 | Description                                                          |
| ------------------------ | -------------------------------------------------------------------- |
| `DATABASE_URL`           | PostgreSQL connection string                                         |
| `AUTH_SECRET_KEY`        | JWT signing secret                                                   |
| `AUTH_ALGORITHM`         | JWT algorithm (default: `HS256`)                                     |
| `CORS_ORIGINS`           | Comma-separated list of allowed origins                              |
| `ENVIRONMENT`            | `development` or `production`                                        |
| `BREVO_API_KEY`          | Brevo transactional email API key                                    |
| `BREVO_SENDER_EMAIL`     | Verified Brevo sender address                                        |
| `BREVO_APP_BASE_URL`     | Public app origin used to build verification links                   |
| `PUSH_VAPID_PUBLIC_KEY`  | VAPID public key, sent to the frontend to create a push subscription |
| `PUSH_VAPID_PRIVATE_KEY` | VAPID private key used to sign outgoing push messages                |
| `PUSH_VAPID_SUBJECT`     | VAPID contact subject, e.g. `mailto:admin@example.com`               |
| `PUSH_REMINDER_SECRET`   | Shared secret required to call `POST /internal/push/send-reminders`  |
