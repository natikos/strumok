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

| Secret                 | Description                   |
| ----------------------- | ------------------------------ |
| `FASTAPI_CLOUD_TOKEN`   | FastAPI Cloud deploy token     |
| `FASTAPI_CLOUD_APP_ID`  | FastAPI Cloud app identifier   |

## Push Reminders

Deadline push reminders run outside the web process, as a scheduled GitHub
Actions workflow (`.github/workflows/reminders.yml`) rather than an
in-process scheduler — FastAPI Cloud may run more than one instance or scale
to zero, and an in-process scheduler would duplicate or silently skip a run.
The workflow calls `POST /internal/push/send-reminders` a few times per
reminder day (day 1 and day 5, Kyiv morning); the endpoint is idempotent per
`(period, variant)`, so a repeated or overlapping call never double-sends.

### Required GitHub Secrets (reminders workflow)

| Secret               | Description                                                        |
| --------------------- | -------------------------------------------------------------------- |
| `AUTH_INTERNAL_SECRET` | Same value as the backend's `AUTH_INTERNAL_SECRET` env var           |
| `APP_BASE_URL`         | Public origin of the deployed app, e.g. `https://strumok.example.com` |

If a scheduled run fails, GitHub's own workflow-failure notification is the
only alert — turn on "Notify me for failed workflows" in GitHub notification
settings for this repo. GitHub also disables a scheduled workflow after 60
days of repo inactivity; a push or manual `workflow_dispatch` run re-enables
it.

## Environment Variables

| Variable                 | Description                                               |
| ------------------------- | ----------------------------------------------------------- |
| `DATABASE_URL`            | PostgreSQL connection string                                |
| `AUTH_SECRET_KEY`         | JWT signing secret                                           |
| `AUTH_ALGORITHM`          | JWT algorithm (default: `HS256`)                              |
| `AUTH_INTERNAL_SECRET`    | API secret for internal endpoints (push, webhooks, cron jobs) |
| `CORS_ORIGINS`            | Comma-separated list of allowed origins                      |
| `ENVIRONMENT`             | **Required.** `development` or `production` — no default, startup fails otherwise |
| `BREVO_API_KEY`           | Brevo transactional email API key                             |
| `BREVO_SENDER_EMAIL`      | Verified Brevo sender address                                 |
| `BREVO_APP_BASE_URL`      | Public app origin used to build verification links            |
| `PUSH_VAPID_PUBLIC_KEY`   | VAPID public key for Web Push notifications                   |
| `PUSH_VAPID_PRIVATE_KEY`  | VAPID private key for Web Push notifications                  |
| `PUSH_VAPID_SUBJECT`      | Contact URI (`mailto:` or URL) sent with Web Push requests    |
