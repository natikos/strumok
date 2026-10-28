# Operations

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

`.github/workflows/db-backup.yml` (schedule only, no manual trigger) runs
`pg_dump -Fc`, encrypts with `age`, and uploads to Backblaze B2 as
`period-close/<kind>-<timestamp>.dump.age`. A failed run emails the repo admins.

| Kind | When (UTC) | Why |
| --- | --- | --- |
| `window-closed` | day 6, 06:00 | submission window (days 1–5 Kyiv) is over |
| `payments-verified` | day 11, 18:00 | bank receipt is in, who paid what is recorded |

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

### Restore

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
