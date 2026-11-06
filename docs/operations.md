# Operations

Runbook for the running production system. Local setup is in
[development.md](development.md); how releases work is in [deployment.md](deployment.md).

| Situation | Section |
| --- | --- |
| A release failed or the new version is broken | [Failed release](#failed-release) |
| Need data back from a backup | [Restore](#restore) |
| Is the app up? | [Health check](#health-check), [Uptime monitor](#uptime-monitor) |
| Backup missing, setting up backups, project paused | [Database backups](#database-backups), [Keep-alive](#keep-alive) |
| No admin exists yet | [First admin](#first-admin) |
| A resident asks to correct, export or delete their data | [Personal data requests](#personal-data-requests) |

## First admin

Sign-up is closed (`POST /auth/register` always answers `registrationClosed`) and
only an admin can invite users, so the very first admin is made by hand in SQL.
After that, an admin promotes others from the admin user screen
(`PATCH /admin/users/{id}` with `is_admin`), which is audited; at least one active
admin must remain (`lastAdminRequired`).

1. Take a backup first (`pg_dump "$DATABASE_URL" -Fc -f pre-admin.dump`).
2. The user must already exist: an account created by an earlier invite, or one
   inserted by hand with a bcrypt `password_hash`.
3. Promote it, checking that exactly one row changed:

   ```sql
   UPDATE users SET is_admin = true, email_verified = true
   WHERE email = 'head@example.com';
   ```

This bypasses the audit log, so note who ran it and when. The e2e suite creates
its admin through the test-only `POST /__e2e/users` instead, which exists only under
`ENVIRONMENT=e2e` and never in production.

## Health check

`GET /health` runs `SELECT 1` against Postgres (connect timeout 3 s).

| Response | Meaning |
| --- | --- |
| `200 {"status": "ok"}` | App and database reachable |
| `503 {"status": "degraded", "db": "unreachable"}` | App is up, database is not |

## Uptime monitor

UptimeRobot (free plan) monitor `Strumok /health`, created by hand in the
UptimeRobot dashboard:

- Type HTTP(s), URL `https://strumok.fastapicloud.dev/health`, interval 5 minutes.
- Alert contact: the head's email, after 2 consecutive failures.

It also keeps Supabase awake. It lives in the monitoring service, not in this
repo.

## Database backups

Supabase's free tier has no backups or PITR, so these dumps are the only backup.

`.github/workflows/db-backup.yml` runs on a schedule and is also called by every
release (`deployment.yml`). It runs `pg_dump -Fc`, encrypts with `age`, and
uploads to Backblaze B2 as `period-close/<kind>-<timestamp>.dump.age`, or
`release/release-<tag>-<timestamp>.dump.age` for a release. A failed run emails
the repo admins. There is no manual trigger.

| Kind | When (UTC) | Why |
| --- | --- | --- |
| `window-closed` | day 6, 06:00 | submission window (days 1–5 Kyiv) is over |
| `payments-verified` | day 11, 18:00 | bank receipt is in, who paid what is recorded |
| `release-<tag>` | each release, before migrating | restore point if a migration or deploy goes wrong |

Anything written between runs is not backed up until the next one. A B2
lifecycle rule hides files after 90 days and deletes them a day later (about 6
dumps).

### Setup (owner, once)

1. **B2**: private bucket, default encryption on, holding only these backups.
   Create an application key limited to it. Lifecycle Settings → custom rule:
   empty prefix, days till hide `90`, days till delete `1`.
2. **DB role**, in the Supabase SQL editor:
   ```sql
   create role backup_ro login password '<generated>';
   grant pg_read_all_data to backup_ro;
   ```
3. **Age keypair**: the head runs `age-keygen -o strumok-backup.key`, keeps two
   offline copies, and never commits it. Losing it makes every backup unreadable.
4. **Variables** (Settings → Secrets and variables → Actions):
   `BACKUP_AGE_RECIPIENT` (the `age1...` public key), `APP_ORIGIN`
   (`https://strumok.fastapicloud.dev`).
5. **Secrets**: `BACKUP_DATABASE_URL` (the *session pooler* string, user
   `backup_ro.<project-ref>`; the direct host is IPv6-only and runners are IPv4),
   `BACKUP_S3_ACCESS_KEY_ID`, `BACKUP_S3_SECRET_ACCESS_KEY`,
   `BACKUP_S3_ENDPOINT` (`https://s3.<region>.backblazeb2.com`),
   `BACKUP_S3_REGION`, `BACKUP_S3_BUCKET`.

The first real check is the first scheduled run (day 6): confirm the object
appears, then do the restore drill from it.

### Keep-alive

Free-tier projects pause after about a week idle, which would fail the dump.
`.github/workflows/keep-alive.yml` calls `$APP_ORIGIN/health` (`SELECT 1`) every
3 days and fails, emailing the admins, on a non-200. Unconfirmed: whether
`SELECT 1` counts as activity for Supabase. Check the dashboard after a week; if
it still pauses, make the check read a table. If a run fails because the project
is paused, unpause it; the missed dump waits for the next run.

GitHub disables scheduled workflows on public repos after 60 days without repo
activity, which would silently stop both workflows. Re-enable them from the
Actions tab, or make the repo private (the rule doesn't apply there).

## Failed release

`deployment.yml` migrates, deploys, then checks `/health`. What happens on failure:

- **Migration fails**: Postgres rolls the transaction back; production stays at
  its previous revision and nothing is deployed. Fix and re-tag.
- **Deploy or health check fails after migrating**: the `release-failed` job
  ends the run red and nothing is redeployed or restored. The schema is at head.
  Check which version is serving, then fix forward with a new tag, or redeploy
  an older tag with `workflow_dispatch` + `rollback`. That is safe only if the
  release applied no `# contract:` migration; otherwise the old code may not run
  on the new schema, so fix forward or restore the release dump. Don't restore
  while something may still be writing.

Restoring the `release/` dump (below) is a deliberate manual step that loses every
write since the backup. The workflow never downgrades or restores by itself.

## Restore

Needs `age`, `pg_restore` 17, the `aws` CLI, and the private key.

```bash
export AWS_ACCESS_KEY_ID=... AWS_SECRET_ACCESS_KEY=... AWS_DEFAULT_REGION=<region>
export AWS_REQUEST_CHECKSUM_CALCULATION=when_required AWS_RESPONSE_CHECKSUM_VALIDATION=when_required
EP=https://s3.<region>.backblazeb2.com
aws s3 ls s3://<bucket>/period-close/ --endpoint-url $EP
aws s3 cp s3://<bucket>/period-close/<file>.dump.age . --endpoint-url $EP
age -d -i strumok-backup.key <file>.dump.age > restore.dump

docker compose up -d
docker compose exec -T database createdb -U postgres restore_check
pg_restore --no-owner --no-privileges \
  -d postgresql://postgres:postgres@localhost:5432/restore_check restore.dump
```

To restore production, load into a fresh database, verify it as below, then
point `DATABASE_URL` at it.

### Quarterly restore drill

Restore the latest dump as above and check that row counts per table match the
live database. Once the billing ledger exists, also check that Σ
`household_charges.total_uah` per closed period equals that period's bill total.
Record the date and result on a comment of the tracking issue.

## Personal data requests

Residents are told (at `/privacy`) to ask the head to correct, export or delete
their data. Handle each request by hand, and confirm the person by replying to
the email on their account.

- **Correct**: fix name or email from the admin user management screen, or
  with an `UPDATE` on `users` for anything the UI doesn't cover. Readings are
  corrected through the admin reading screen, never by editing rows.
- **Export**: give the person their `users` row, their households' meter
  readings, and their charges and payments (`household_charges`, payments),
  as a spreadsheet or CSV sent to the email on the account.
- **Delete**: anonymize, don't drop. Replace `users.name` and `users.email`
  with a placeholder (for example `deleted-<id>@invalid`), clear the password
  hash and any push subscriptions, and keep the readings, charges and payments
  because the co-op's accounts must survive. `household_charges` is immutable
  by trigger, so never delete from it.

Backups still contain the old values until they age out (about 90 days); say
so when you confirm a deletion. Record the request and date in the audit log
or the tracking issue.
