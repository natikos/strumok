# Operations

## Health check

`GET /health` runs `SELECT 1` against Postgres (connect timeout 3 s).

| Response | Meaning |
| --- | --- |
| `200 {"status": "ok"}` | App and database reachable |
| `503 {"status": "degraded", "db": "unreachable"}` | App is up, database is not |

## Uptime monitor

Point an external HTTP monitor (e.g. UptimeRobot, Better Stack) at
`https://<app-origin>/health`:

- Check interval: 5 minutes; expect status `200`.
- Alert contact: the head's email, after 2 consecutive failures.

The monitor lives in the monitoring service, not in this repo, so it has to be
created by hand once the production origin is known. Record its name here when
it exists.
