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

The workflow (`.github/workflows/deployment.yml`) runs these jobs in order, one
release at a time (`production-release` concurrency group, never cancelled):

1. `preflight`: the tag must be `v*` and reachable from `main`; `ci.yml` must
   have succeeded on its commit; `backend/scripts/check_migrations.py
   --allow-behind` (read-only) reads production's revision. Production at a
   revision the tag doesn't know fails the release.
2. `backup`: calls `db-backup.yml` (`release/release-<tag>-<timestamp>.dump.age`
   in the backup bucket), so every release has a fresh pre-migration dump.
3. `migrate` (only if migrations are unapplied): `alembic upgrade head` with
   `PROD_DATABASE_URL_MIGRATE`, then re-runs the check. Alembic on Postgres
   applies the whole upgrade in one transaction, so a failed migration leaves
   production at the revision it started from.
4. `deploy`: builds the frontend and runs `uv run fastapi deploy`
   (`.github/actions/deploy`).
5. `smoke`: polls `$APP_ORIGIN/health` for 3 minutes. It proves the app is up
   and reaches Postgres, not which version is running.
6. `release-failed` (only if migrate succeeded and deploy or smoke failed):
   fails the run with a pointer to the runbook. Nothing is redeployed or
   restored automatically: the schema stays at head, and whether the previous
   tag runs on it depends on whether a `# contract:` migration was applied.
   Migrations are **never** downgraded automatically: most downgrades drop
   tables or columns holding ledger data, and `0013` cannot be undone. Restoring
   the release dump is manual, see [operations.md](operations.md#failed-release).

### Migrations

Migrations now run as part of the release; do **not** run them by hand first.
Every migration must stay backward-compatible with the previously deployed
code (add first, remove in a later release), because a failed release leaves the
new schema running under the old code. CI enforces this
(`backend/tests/test_migration_safety.py`, from `0019` on): a migration that
drops, renames or alters something, adds a required column without a server
default, or runs `DROP`/`RENAME` SQL fails the test unless it has a
`# contract: <why>` comment. A marked migration is allowed, but a failed release
that applied it needs manual recovery.

**One-time prod baseline:** `0000` was generated from the models, not from prod.
Diff a `pg_dump --schema-only` of prod against a fresh `alembic upgrade 0000`
schema, fix any drift in a new migration, then `alembic stamp 0000` in prod
(do not run `0000` there). `0001` adds a unique index on
`electricity_rates.effective_from` and fails if prod has duplicates.

You can also trigger a deployment manually from the GitHub Actions UI
(**workflow_dispatch**). It needs a `tag` input. Tick `rollback` to redeploy an
older tag as-is, skipping backup and migrations.

### Required GitHub Secrets

| Secret                 | Description                  |
| ---------------------- | ---------------------------- |
| `FASTAPI_CLOUD_TOKEN`  | FastAPI Cloud deploy token   |
| `FASTAPI_CLOUD_APP_ID` | FastAPI Cloud app identifier |
| `PROD_DATABASE_URL_READONLY` | Read-only production connection string for the migrations preflight |
| `PROD_DATABASE_URL_MIGRATE` | Production connection string of a role that can run DDL, used only by the `migrate` job. Use the Supabase *session* pooler string (Alembic needs session semantics) and a dedicated role, not the superuser. Prefer storing it in the `production` GitHub environment, restricted to `v*` tags |

### Required GitHub variable and environment

- **Variable `APP_ORIGIN`** (Settings → Secrets and variables → Actions →
  Variables): the public app origin, e.g. `https://example.fastapicloud.dev`.
  `preflight` fails the release when it is empty, so a missing value can't
  turn a good deploy into a failed smoke check.
- **Environment `production`** (Settings → Environments): the `migrate` and
  `deploy` jobs declare it. GitHub creates it unprotected on first use, so
  create it up front, restrict deployment tags to `v*`, and keep
  `PROD_DATABASE_URL_MIGRATE` there as an environment secret rather than a
  repository secret.

## Backups

The database is backed up on day 6 and day 11 of each month and before every release by `.github/workflows/db-backup.yml`. Setup, restore, and
the quarterly drill are in [operations.md](operations.md#database-backups).

## Push Reminders

Deadline push reminders run on an in-process APScheduler
(`backend/app/api/push/scheduler.py`), started from the app's lifespan. An
hourly job (minute 0 UTC) sends the `opening` variant on Kyiv day 1 and the
`final` variant on day 5 to each user whose chosen hour (`users.reminder_hour`,
Kyiv time, default 09:00) has arrived. The instance must be awake on those
days; if it is put to sleep after the 10th, wake it before the 1st. Users are
claimed in `NotificationLog` before sending, so overlapping runs or multiple
instances notify each `(user, period, variant)` at most once.

## Bank Statement Inbox

When the `IMAP_*` variables are set, the same scheduler runs an hourly check
(minute 30 UTC) of the mailbox, read-only, for messages from the allow-listed
senders in the last 45 days. A message is imported only if the receiving
server's top `Authentication-Results` (authserv-id `IMAP_AUTHSERV_ID`) shows
`dmarc=pass` for the sender's domain (or a `dkim=pass` aligned with it) and it carries a `.csv` attachment under
1 MB. Imported credits go to the review queue like an upload. Each message is
recorded once in `bank_mail_fetches` (`received`, `imported` or `rejected` with
a reason code). Admins can run `POST /admin/bank-statements/check-inbox` if the
instance was asleep. Gmail needs 2-step verification to issue the app password.

## Environment Variables

| Variable                 | Description                                                                       |
| ------------------------ | --------------------------------------------------------------------------------- |
| `DATABASE_URL`           | PostgreSQL connection string                                                      |
| `AUTH_SECRET_KEY`        | JWT signing secret                                                                |
| `AUTH_ALGORITHM`         | JWT algorithm (default: `HS256`)                                                  |
| `AUTH_ACCESS_TOKEN_EXPIRATION` | Access token lifetime in minutes (default: `60`); refreshed via `/auth/refresh` |
| `CORS_ORIGINS`           | Comma-separated list of allowed origins                                           |
| `ENVIRONMENT`            | **Required.** `development` or `production` — no default, startup fails otherwise. `e2e` exists only for the Playwright suite (shifted clock, test-only routes) and refuses any non-local database; never set it here |
| `BREVO_API_KEY`          | Brevo transactional email API key                                                 |
| `BREVO_SENDER_EMAIL`     | Verified Brevo sender address                                                     |
| `BREVO_APP_BASE_URL`     | Public app origin used to build verification links                                |
| `PUSH_VAPID_PUBLIC_KEY`  | VAPID public key for Web Push notifications                                       |
| `PUSH_VAPID_PRIVATE_KEY` | VAPID private key for Web Push notifications                                      |
| `PUSH_VAPID_SUBJECT`     | Contact URI (`mailto:` or URL) sent with Web Push requests                        |
| `IMAP_USER`              | Co-op mailbox that receives the accountant's statement (ingest is off until set)  |
| `IMAP_PASSWORD`          | Gmail app password for `IMAP_USER`. Secret: never log it or commit it             |
| `IMAP_ALLOWED_SENDERS`   | Comma-separated sender addresses whose `.csv` attachments are imported            |
| `IMAP_HOST`              | IMAP server (default `imap.gmail.com`)                                            |
| `IMAP_AUTHSERV_ID`       | Receiving server whose `Authentication-Results` is trusted (default `mx.google.com`) |
| `IMAP_FOLDER`            | Mailbox folder to read (default `INBOX`)                                          |
