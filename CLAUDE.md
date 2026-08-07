@docs/contributing.md
@docs/deployment.md

# Strumok

Electricity billing for a garden cooperative on one shared utility bill. Residents submit monthly meter readings; the head gets consistent per-household accounting. Mobile-first PWA — residents are expected to use it on their phones out in the garden, not at a desk.

## Stack & commands

- **Backend** (`backend/`, Python 3.14 + uv): FastAPI, SQLModel, PostgreSQL (psycopg), JWT in an HttpOnly cookie. Run `uvicorn app.main:app --reload`; lint with `ruff`.
- **Frontend** (`frontend/`, Bun): Vue 3 + TS, Vite, PrimeVue (Aura preset customized in `src/preset.ts`), vue-i18n (en/ua), zod, openapi-fetch, installable PWA (`vite-plugin-pwa`, configured in `vite.config.ts`). `bun run dev` / `bun run lint` / `bun run build` (vue-tsc + vite, outputs to `backend/dist/`).
- **Local Postgres**: `docker compose up -d` from repo root.
- **Tests**: `cd backend && uv run pytest` (needs local Postgres: `docker compose up -d`); `cd frontend && bun run test`. See [docs/testing.md](docs/testing.md).
- **Metrics**: `python3 scripts/project_metrics.py` reports rework, commit-convention compliance, open-issue age, and (with `--coverage`) frontend coverage. Read-only. See [docs/metrics.md](docs/metrics.md) for what it deliberately doesn't measure and why.

## Domain

A `User` owns zero or more `Household`s (garden plots on the shared bill). Each month, on
days 1–5 (`frontend/src/features/meter-readings/deadline.ts`), a resident submits one
`MeterReading` per household for the prior period — cumulative day/night meter values, from
which usage is derived. The head uses these across all households to reconcile the one shared
utility bill. A user can hold multiple households (frontend tracks a "current household" in
localStorage), but a household has at most one owning user.

Per-household billing (turning usage into `amount_charged_uah`) is unimplemented — see
[Known limitations](docs/known-limitations.md).

Keep this section current as the domain evolves — update it in the same change that adds or
changes a concept, not as separate cleanup later.

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

For any request that names a feature or user-facing capability rather than a specific, already-scoped edit (e.g. "build a dashboard", "add reporting", "let residents track X") — don't ask which specialist to use or wait to be told. Work out the pipeline yourself and run it without narrating the routing decision:

1. **Scope first.** If the request is broad or the acceptance criteria aren't obvious from the ask, run `product-owner` before writing any code. Skip it only for edits that are already small and specific (rename a field, fix a bug, tweak a style).
2. **Architecture/data-model calls.** If the feature needs a new table, a new API shape, a cross-cutting decision, or touches auth/household-scoping/money handling, run `tech-lead` to decide the approach before implementing.
3. **UI/flow work.** If the feature has a user-facing screen or interaction, run `ui-ux-designer` for layout/flow before or alongside implementation.
4. **Implement** using the conventions above. Start non-trivial work with the
   `commit-work` skill — it creates the branch, ensures a tracked issue exists,
   and commits each coherent slice as it lands. Commit as you go, not once at
   the end.
5. **Tests.** Once behavior is implemented, run `qa-automation` to add coverage,
   then review its diff and commit it yourself — specialists don't commit.
6. **Ship.** Run `/shipit` when the user asks to land the work. It's a command,
   not a skill: it squash-merges to `main`, so it runs only when the user asks
   for it — never on your own initiative.

**Issue tracking.** Work should be tracked before it's committed. `commit-work`
handles the common path (reuse the number in the request, else search, else
file). Use `create-issue` directly when the user reports something you're *not*
about to fix — "I found X bug" with no fix requested. Don't file duplicates:
both search open issues first.

**Specialists can't commit or file issues.** None of them have `gh` or `Skill`
access; `qa-automation` alone can write files, and only test files. They report
findings — the main agent reviews the diff and commits it. That keeps one
reviewer between generated code and history.

Not every stage applies to every request — a one-screen form may only need product-owner + implementation, not tech-lead. Use judgment on what's overkill, but default to running the relevant specialists rather than asking the user which one to invoke. Still check in with the user on genuinely ambiguous product decisions the specialists can't resolve (e.g. conflicting priorities) — the goal is to remove _tool-routing_ friction, not product judgment calls.
