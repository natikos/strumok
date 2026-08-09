# Known limitations

## Billing is unimplemented

`MeterReading.amount_charged_uah` is never populated by the API — tariffs and the
reserve fund don't exist yet, so a submitted reading always stores the `0` default.
Don't assume billing math exists anywhere in `backend/app/api/`.

The billing formula itself is known:

```
amount_charged_uah = day_usage_kwh × 4.70 + night_usage_kwh × 2.35
```

(4.70 and 2.35 are UAH/kWh day and night rates.) These rates need to live in a
configurable DB table (editable from an admin UI later) rather than being
hardcoded — see [#45](https://github.com/natikos/strumok/issues/45) for this work.

The one exception is `backend/scripts/import_meter_history.py`, which writes real
charged amounts from a CSV import. Its `parse_decimal` currently rounds through
`float` and silently yields `0` on a malformed cell.
