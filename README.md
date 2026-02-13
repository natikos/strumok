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

## Run locally

### 1) Start Postgres

```bash
docker compose up -d
```

### 2) Install all dependencies from project root

```bash
make install
```

If you want to force a specific Python binary (for example Python 3.14.2):

```bash
make install PYTHON=python3.14
```

### 3) Configure env files

```bash
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
```

### 4) Run backend (from project root)

```bash
backend/.venv/bin/uvicorn app.main:app --reload --port 8000 --app-dir backend
```

### 5) Run frontend (from project root)

```bash
npm --prefix frontend run dev
```

App URLs:
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
