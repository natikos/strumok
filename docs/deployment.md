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

1. Build the frontend: `bun run build` (inside `frontend/`)
2. Deploy the backend via FastAPI Cloud CLI: `fastapi-cloud deploy` (inside `backend/`)

## Environment Variables

| Variable | Description |
|---|---|
| `DB_URL` | PostgreSQL connection string |
| `AUTH_SECRET_KEY` | JWT signing secret |
| `AUTH_ALGORITHM` | JWT algorithm (default: `HS256`) |
| `CORS_ORIGINS` | Comma-separated list of allowed origins |
| `ENVIRONMENT` | `development` or `production` |
