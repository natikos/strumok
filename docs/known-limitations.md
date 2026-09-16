# Known limitations

## Electricity rates have no admin UI yet

`MeterReading.amount_charged_uah` is computed on submission from the
`ElectricityRate` table (day/night UAH/kWh rates, versioned per billing
period via `effective_from`) — see `backend/app/api/electricity_rates/`.
Admins can view and add rates through `GET`/`POST /electricity-rates`, but
there's no way to correct a mistaken rate: existing rows are immutable by
design, since editing one would retroactively change already-computed
charges for closed periods.

The one exception is `backend/scripts/import_meter_history.py`, which writes
real charged amounts from a CSV import. Its `parse_decimal` currently rounds
through `float` and silently yields `0` on a malformed cell.
