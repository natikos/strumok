# Known limitations

## Billing is unimplemented

`MeterReading.amount_charged_uah` is never populated by the API — tariffs and the
reserve fund don't exist yet, so a submitted reading always stores the `0` default.
Don't assume billing math exists anywhere in `backend/app/api/`.

The one exception is `backend/scripts/import_meter_history.py`, which writes real
charged amounts from a CSV import. Its `parse_decimal` currently rounds through
`float` and silently yields `0` on a malformed cell.
