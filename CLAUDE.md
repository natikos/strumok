@docs/contributing.md
@docs/deployment.md

# Strumok

Electricity billing for a garden cooperative on one shared utility bill. Residents submit monthly meter readings; the head gets consistent per-household accounting.

## Stack & commands

- **Backend** (`backend/`, Python 3.14 + uv): FastAPI, SQLModel, PostgreSQL (psycopg), JWT in an HttpOnly cookie. Run `uvicorn app.main:app --reload`; lint with `ruff`.
- **Frontend** (`frontend/`, Bun): Vue 3 + TS, Vite, PrimeVue (Aura preset customized in `src/preset.ts`), vue-i18n (en/ua), zod, openapi-fetch. `bun run dev` / `bun run lint` / `bun run build` (vue-tsc + vite, outputs to `backend/dist/`).
- **Local Postgres**: `docker compose up -d` from repo root.
- No test suite exists yet — adding one means bootstrapping pytest / Vitest from scratch.

## Domain

- `User` — account; `is_admin`, `email_verified`, theme/language preferences.
- `Household` — cooperative plot, owned by at most one user (`households.user_id`, nullable). A user may own several; the frontend keeps a "current household" in localStorage.
- `MeterReading` — one row per `(household_id, period)` (period is `YYYY-MM`, unique constraint). Stores cumulative `day/night_meter_value`, derived `day/night_usage_kwh` (current − previous reading), and `amount_charged_uah`.
- `amount_charged_uah` is **not populated by any code path yet** — tariffs and the reserve fund are unimplemented. Don't assume billing math exists.
- Submission window is days 1–5 of the month (`frontend/src/features/meter-readings/deadline.ts`).

## Conventions

- **Errors**: `HTTPException.detail` is a stable camelCase code (`noHouseholdMembership`, `periodAlreadySubmitted`), never user-facing text. Services raise domain exceptions; routes translate them and declare each one in a `responses` dict with `ErrorOut` + example (see `backend/app/api/meter_readings/routes.py`).
- **Backend module shape**: `backend/app/api/<feature>/{routes,schemas,service}.py`. No DB access in routes.
- **Household scoping**: every household-bound route resolves access through a dependency that verifies ownership and 403s otherwise (`require_household_id`). Follow that pattern for new routes.
- **Money/usage**: `Decimal` end to end in the backend; JSON emits them as strings, so the frontend parses.
- **Generated types**: `frontend/src/shared/api/generated/openapi.ts` is produced by `bun run api:types` against a running backend. Never hand-edit; regenerate after changing schemas.
- **Migrations**: hand-written SQL in `backend/migrations/`, applied manually. `init_db()` only runs `create_all` in development. No Alembic.
- **Frontend layout**: `features/` (domain logic + components), `pages/` (routed views), `shared/`, `layouts/`. Aliases `@/`, `@features`, `@pages`, `@shared`, `@utils`. Components under those dirs and all PrimeVue components are auto-imported — don't add explicit imports.
- **Styling**: scoped SCSS with BEM, `--s-*` design tokens from `src/preset.ts` (check there before hand-rolling colors), `layout` SCSS module auto-injected. Mobile viewport first, minimum supported width **360px** — write base styles for 360px, then layer on wider layouts with `@include layout.respond-to("sm"|"md"|"lg"|"xl")` (`frontend/src/shared/styles/_layout.scss`) instead of a new hardcoded `@media` breakpoint. Grid/flex children holding text or inputs need `min-width: 0` or they can force overflow at 360px.

## When to delegate

Specialists live in `.claude/agents/`: `tech-lead` (architecture, review, security, CI/CD gate), `product-owner` (scope + acceptance criteria before building), `qa-automation` (tests), `ui-ux-designer` (flows, layout, usability).
