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

| Secret | Description |
|---|---|
| `FASTAPI_CLOUD_TOKEN` | FastAPI Cloud deploy token |
| `FASTAPI_CLOUD_APP_ID` | FastAPI Cloud app identifier |

## Environment Variables

| Variable | Description |
|---|---|
| `DB_URL` | PostgreSQL connection string |
| `AUTH_SECRET_KEY` | JWT signing secret |
| `AUTH_ALGORITHM` | JWT algorithm (default: `HS256`) |
| `CORS_ORIGINS` | Comma-separated list of allowed origins |
| `ENVIRONMENT` | `development` or `production` |
