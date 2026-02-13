# Strumok

Starter project for a garden cooperative electricity reporting system.

## Stack

- Frontend: Vue 3 + Vite + Pinia + Vue Router
- Backend: FastAPI + SQLAlchemy + JWT auth
- Database: Postgres (local via Docker compose, cloud via Supabase/Neon)

## Features in this scaffold

- User registration and login
- JWT authentication
- Submit monthly meter reading (allowed only on days 1-5 UTC)
- Automatic usage calculation from previous meter value
- User reading history
- Admin view for all readings
- Admin API endpoint to promote users

## Quick start (single command)

First time only:

```bash
make install
```

Then every time you want to run development environment:

```bash
make dev
```

This command will:
- start Postgres (`docker compose up -d postgres`)
- create `backend/.env` and `frontend/.env` from examples if missing
- run backend on `http://localhost:8000`
- run frontend on `http://localhost:5173`

Stop everything started by `make dev` with `Ctrl+C`.

## App URLs

- Frontend: `http://localhost:5173`
- Backend API docs: `http://localhost:8000/docs`

## First admin user

1. Register normally in the app.
2. Temporarily set `is_admin=true` for that user in DB (or use SQL).
3. Then admin can promote other users via API:

```bash
POST /api/users/promote
Authorization: Bearer <admin_token>
{
  "email": "user@example.com"
}
```

## Suggested cloud deployment

- Frontend: Cloudflare Pages
- Backend: Render (Python web service)
- DB/Auth: Supabase Postgres/Auth

Environment variables for backend (`backend/.env`):

```env
SECRET_KEY=replace-with-a-long-random-string
DATABASE_URL=postgresql+psycopg://USER:PASSWORD@HOST:5432/DBNAME
CORS_ORIGINS=https://your-frontend-domain.com
ACCESS_TOKEN_EXPIRE_MINUTES=1440
```
