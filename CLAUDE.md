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
days 1–5 Kyiv time, a resident submits one `MeterReading` per household for the prior period —
cumulative day/night meter values, from which usage is derived. The submission window is
computed client-side in Kyiv time (`frontend/src/shared/utils/deadline.ts`), not the device's
timezone; the backend (`backend/app/core/domain/billing.py`) uses Kyiv time for the current
period but does not enforce the window. The head uses these across all households to reconcile
the one shared utility bill. A user can
hold multiple households (frontend tracks a "current household" in localStorage), but a
household has at most one owning user.

Billing lives in a ledger. `MeterReading` is a raw fact (meter values + `source`); usage is
derived from consecutive readings (`derive_usage`, the first reading is a baseline). A period
is `open` or `closed` (`billing_periods`); closing writes immutable `household_charges` rows
(a DB trigger rejects UPDATE/DELETE) computed by the pure `compute_period_statement` in
`backend/app/core/domain/billing.py`. Amounts round `ROUND_HALF_UP` once per final line.
`GET /billing/statements` returns a household's closed charges plus a read-time
`provisional` line for the open period (never stored). History before go-live was
backfilled as closed periods. Closing needs the utility bill (`PUT /admin/periods/{period}/bill`)
and splits bill − Σ tariff across households pro-rata by usage (largest remainder, so charges
equal the bill exactly). At close, `create_estimates` writes a `source='estimate'` reading for each active household with a reading history but none for the period (owner or not): a virtual cumulative value, previous reading + the last real month's usage, or the median of the period's real submissions when there is no usage history (or it was zero), so the next real reading trues it up. Households with no reading at all are skipped. The close response (`POST /admin/periods/{period}/close`) lists `unowned_estimated` households (estimated, no owner, so the charge has `owner_user_id=None`), and the admin close card shows them as a warning. An estimated household pays a 30% penalty on its estimated tariff only (not its loss share); the penalties are credited pro-rata by usage to the households that submitted, so charges still equal the bill (no penalty if nobody submitted). A meter replacement is a `meter_segments` row (`POST /admin/households/{id}/meter-change`): the period's usage is (old final − previous reading) + (reading − new start), and it clears a `decrease` flag. A household's opening values are a `baseline` reading (`kind='baseline'` on `POST /admin/households/{id}/readings`, or the starting-values fields on household creation; left empty, a new household gets a 0/0 baseline, as a brand-new meter, so its first resident reading is billed in full): never billed, the first resident reading is measured against it. Ownership is history: `household_ownerships` (`valid_from`/`valid_to`, one open row per household), and `households.user_id` mirrors the open row — change owners only through `app.core.ownership.set_owner`. A charge's billed owner is whoever held the plot at the period's end (Kyiv). Reassigning (`PATCH /admin/households/{id}/owner`) needs a handover meter reading and, if the outgoing owner owes money, `acknowledge_balance`; once a plot has changed hands, resident endpoints filter readings, charges, adjustments and balance to the current owner's tenure, and `GET /me/statements` shows each owner everything they were billed, including plots they gave up (`has_previous_owner` marks a plot someone else held first). The dashboard tells an old owner they no longer own the plot, history lists gave-up plots read-only under "Past households" and tells a new owner that earlier records belong to the previous owner; the balance strip still counts debt on gave-up plots. Balances start from an opening balance: `opening_balances`, one row per household (signed `amount_uah`, positive = owes, plus `as_of`), set once via `POST /admin/households/{id}/opening-balance` or `backend/scripts/import_opening_balances.py` (the sheet's "Стан рахунку", sign flipped). `get_balance` adds it to what is owed and payments settle it before any period; a wrong figure is corrected by a payment or adjustment, never edited. The co-op's IBAN and recipient (`payment_details`, one row) are set by the head via `PUT /admin/payment-details` (audited, UA IBAN checksum validated) and read by residents at `GET /billing/payment-details`; the dashboard's Pay sheet shows them with copy buttons next to the current plot's balance. There are no bank deep links yet (unverified), and payment status stays manual. A rate can be edited or
deleted until a closed period was billed with it. A reading carries only meter values: usage
is derived (`derive_reading_usage`) and charges live in `household_charges`. The spreadsheet
import (`backend/scripts/import_meter_history.py`) writes the reading plus a closed period and
a charge with the sheet's exact amount, never recomputed from rates, and refuses the current
period.

An admin uploads the accountant's bank statement at `POST /admin/bank-statements` (multipart `.csv`, 1 MB, 5,000 rows, parsed in memory and never stored): credits are inserted idempotently (re-uploading the same sha256 or overlapping files adds nothing), debits are skipped, and the response reports new/duplicate/skipped counts and `covered_through`. With the `IMAP_*` env set, `backend/app/api/bank/inbox.py` fetches the accountant's emailed `.csv` from allow-listed, DMARC/DKIM-authenticated senders hourly (and on `POST /admin/bank-statements/check-inbox`) through the same `import_statement` (system actor, no uploader), recording each message once in `bank_mail_fetches` as received/imported/rejected with a reason code. Each import is audited with counts only, and admins are notified when rows join the review queue. Credits become payments only through the review queue (`/admin/bank-transactions`, `backend/app/api/bank/review.py`): an admin confirms a credit (all-or-nothing split across households, sum equals the row; a `transfer` payment owned by whoever held the plot on the operation date, rejected on or before the household's `opening_balances.as_of`), links it to an existing manual transfer (same amount, within 5 days), or dismisses it. A credit's state is derived, not stored (live linked payment = confirmed, `dismissed_at` = dismissed, else queued); each action locks the row and a repeat returns 409 `bankTransactionResolved`. Voiding one payment of a confirmed credit voids its siblings, so the credit returns to the queue. Payer name and purpose never reach `Payment.note` or the audit log. The queue suggests households deterministically (`backend/app/api/bank/matching`, computed on read, no LLM, never from payer tax ID or IBAN): `STR-<household id>` references in the purpose (several for a split), else a single fuzzy payer-surname match against active household names, else none. A suggestion only pre-fills the confirm dialog with its reason. The Pay sheet's purpose lists the `STR-<id>` of every household the user holds (`frontend/src/shared/utils/paymentPurpose.ts` mirrors `household_reference`). `GET /billing/bank-coverage` reports the max `covered_through` over imported files and `awaiting_statement` (true when none was ever imported or the newest is more than 21 days old, since statements arrive about days 1–6 and ~17); admins also get `last_imported_at`. The dashboard and the admin Bank tab show "payments included up to DD.MM" or an awaiting notice (`BankCoverageNotice`). Shortfall (`backend/app/api/billing/shortfall.py`): each *app-closed* period (`closed_by_user_id` set; backfilled periods have none) is due on the 20th after the month following it (or the next 20th after a late close). The window is the newest such period whose due date max `covered_through` has reached, provided no queued credit dated on or before that date remains, so closing a later period does not hide an earlier one. `notify_shortfall` runs after each import, close, and queue confirm/link/dismiss: it tells each owner who still owes their overdue amount (balance minus unpaid later periods) once per (user, period) via `NotificationLog` (overpaid get nothing; indebted ownerless households go to admins). `GET /billing/shortfall` drives the dashboard's persistent `ShortfallNotice` while the household owes while the household owes.

Deadline push reminders go out on days 1 and 5 at each user's chosen Kyiv hour
(`User.reminder_hour`, default 9, set via `PATCH /auth/preferences`).
Users with no push subscription get the reminder by email (Brevo) instead.

Keep this section current as the domain evolves — update it in the same change that adds or
changes a concept, not as separate cleanup later.

## Conventions

- **Errors**: `HTTPException.detail` is a stable camelCase code (`noHouseholdMembership`, `periodAlreadySubmitted`), never user-facing text. Services raise domain exceptions; routes translate them and declare each one in a `responses` dict with `ErrorOut` + example (see `backend/app/api/meter_readings/routes.py`).
- **Backend module shape**: `backend/app/api/<feature>/{routes,schemas,service}.py`. No DB access in routes.
- **Household scoping**: every household-bound route resolves access through a dependency that verifies ownership and 403s otherwise (`require_household_id`). Follow that pattern for new routes.
- **Money/usage**: `Decimal` end to end in the backend; JSON emits them as strings, so the frontend parses.
- **Prefer installed libraries**: don't hand-roll logic (date math, formatting, etc.) that an already-installed dependency covers — e.g. use `date-fns` (already a dependency, see `frontend/src/shared/utils/deadline.ts`) instead of native `Date` arithmetic.
- **Reuse before writing**: before adding a helper, check `frontend/src/shared/` (and `frontend/src/utils/`) for existing logic that already does it — e.g. formatting a meter value is `frontend/src/shared/utils/format.ts`, not a copy in each component. If you find the same logic duplicated across components while implementing something new, extract it to `shared/` rather than adding a third copy.
- **Generated types**: `frontend/src/shared/api/generated/openapi.ts` is produced by `bun run api:types` against a running backend. Never hand-edit; regenerate after changing schemas.
- **Migrations**: Alembic (`backend/alembic/versions/`). Change a model, then `cd backend && uv run alembic revision --autogenerate -m <name> --rev-id <NNNN>`, review the generated file, and `uv run alembic upgrade head`. CI fails on model/migration drift (`alembic check`). Never edit an applied migration; keep them backward-compatible (expand/contract). Production refuses to start if the DB is behind head (`schemaOutdated`). Tests still use `create_all`.
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
