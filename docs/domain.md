# Domain

How Strumok models the co-op's billing. Keep this file current: update it in the
same change that adds or changes a concept, not as separate cleanup later.
(CLAUDE.md imports it, so Claude Code reads it on every session.)

Contents: [Core concepts](#core-concepts) · [Submission window](#submission-window) ·
[Billing ledger](#billing-ledger) · [Closing a period](#closing-a-period) ·
[Estimates and the penalty](#estimates-and-the-penalty) ·
[Baselines and meter replacement](#baselines-and-meter-replacement) ·
[Ownership](#ownership) · [Balances and payments](#balances-and-payments) ·
[Bank statements](#bank-statements) · [Shortfall notices](#shortfall-notices) ·
[Reminders](#reminders) · [Imports](#imports)

## Core concepts

- A `User` owns zero or more `Household`s (garden plots on the shared bill). A
  household has at most one owning user.
- A user can hold several households; the frontend tracks a "current household"
  in localStorage.
- Each month a resident submits one `MeterReading` per household for the prior
  period: cumulative day/night meter values, from which usage is derived.
- The administrator uses readings across all households to reconcile the one shared
  utility bill.
- A reading carries only meter values (plus `source`). Usage is derived
  (`derive_reading_usage`); charges live in `household_charges`.

## Submission window

Days 1–5 of the month, Kyiv time. The window is computed client-side in Kyiv time
(`frontend/src/shared/utils/deadline.ts`), not the device's timezone. The backend
(`backend/app/core/domain/billing.py`) uses Kyiv time for the current period but
does not enforce the window.

## Billing ledger

- `MeterReading` is a raw fact (meter values + `source`). Usage comes from
  consecutive readings (`derive_usage`); the first reading is a baseline.
- A period is `open` or `closed` (`billing_periods`). Closing writes immutable
  `household_charges` rows (DB triggers reject UPDATE, DELETE and TRUNCATE; the same holds for
  `charge_adjustments`, `audit_log` and `opening_balance_corrections`. Only the
  e2e reset and tests lift the TRUNCATE guard, per transaction), computed by
  the pure `compute_period_statement` in `backend/app/core/domain/billing.py`.
- Amounts round `ROUND_HALF_UP` once per final line.
- `GET /billing/statements` returns a household's closed charges plus a read-time
  `provisional` line for the open period (never stored).
- History before go-live was backfilled as closed periods.
- A rate can be edited or deleted until a closed period was billed with it.

## Closing a period

- Closing needs the utility bill (`PUT /admin/periods/{period}/bill`).
- The bill minus the sum of tariff is split across households pro-rata by usage
  (largest remainder), so charges equal the bill exactly.
- `POST /admin/periods/{period}/close` closes the period.

## Estimates and the penalty

At close, `create_estimates` writes a `source='estimate'` reading for each active
household that has a reading history but none for the period (owner or not).

- The estimate is a virtual cumulative value: previous reading plus the last real
  month's usage. If there is no usage history (or it was zero), it is the median of
  the period's real submissions. The next real reading trues it up.
- Households with no reading at all are skipped.
- The close response lists `unowned_estimated` households (estimated, no owner, so
  the charge has `owner_user_id=None`); the admin close card shows them as a warning.
- An estimated household pays a **30% penalty on its estimated tariff only** (not
  its loss share). The penalties are credited pro-rata by usage to the households
  that submitted, so charges still equal the bill. If nobody submitted, there is
  no penalty.

## Baselines and meter replacement

- **Baseline:** a household's opening values, a reading with `kind='baseline'`
  (`POST /admin/households/{id}/readings`, or the starting-values fields on
  household creation). Never billed; the first resident reading is measured
  against it.
- Left empty, a new household gets a 0/0 baseline, as for a brand-new meter. Its
  first resident reading is billed in full and flagged `zeroBaseline` for the
  head's review before close.
- **Meter replacement** is a `meter_segments` row
  (`POST /admin/households/{id}/meter-change`). The period's usage is
  (old final − previous reading) + (reading − new start). It clears a `decrease`
  flag.

## Ownership

Ownership is history: `household_ownerships` (`valid_from`/`valid_to`, one open row
per household). `households.user_id` mirrors the open row, so **change owners only
through `app.core.ownership.set_owner`**.

- A charge's billed owner is whoever held the plot at the period's end (Kyiv).
- **Reassigning** (`PATCH /admin/households/{id}/owner`, including giving an
  unowned plot to someone other than its last owner) needs a handover meter
  reading and, if the outgoing owner owes money, `acknowledge_balance`.
- A handover on days 1–5 while the reported period is open is recorded as that
  period's reading (`source='admin'`, billed to the outgoing owner) unless one
  exists. The new owner's tenure then starts at that period; otherwise it starts at
  the handover month.
- Once a plot has changed hands, resident endpoints filter readings, charges,
  adjustments and balance to the current owner's tenure.
- `GET /me/statements` shows each owner everything they were billed, including
  plots they gave up (`has_previous_owner` marks a plot someone else held first).
- The dashboard tells an old owner they no longer own the plot. History lists
  gave-up plots read-only under "Past households" and tells a new owner that earlier
  records belong to the previous owner. The balance strip still counts debt on
  gave-up plots.
- A user whose plots were all handed over is not locked out: `/auth/me` reports
  `has_past_households`, and the app shows only the gave-up plots' bills and
  balance, with a Pay sheet for that debt (`GET /billing/payment-details` serves any
  past or current owner).

## Balances and payments

- **Opening balance:** `opening_balances`, one row per household (signed
  `amount_uah`, positive = owes, plus `as_of`). Set once via
  `POST /admin/households/{id}/opening-balance` or
  `backend/scripts/import_opening_balances.py` (the sheet's "Стан рахунку", sign
  flipped).
- `get_balance` adds the opening balance to what is owed; payments settle it before
  any period.
- A wrong opening balance is never edited. It is corrected by an append-only,
  audited, signed `opening_balance_corrections` row with a required reason
  (`POST /admin/households/{id}/opening-balance/corrections`), billed to the
  opening balance's owner.
- **Payment details:** the co-op's IBAN, recipient and optional 8-digit EDRPOU
  (`payment_details`, one row) are set by the administrator via `PUT /admin/payment-details`
  (audited, UA IBAN checksum validated) and read by residents at
  `GET /billing/payment-details`. The dashboard's Pay sheet shows them with copy
  buttons next to the current plot's balance.
- There are no bank deep links yet (unverified), and payment status stays manual.

## Bank statements

**Upload.** An admin uploads the accountant's statement at
`POST /admin/bank-statements` (multipart `.csv`, 1 MB, 5,000 rows, parsed in memory
and never stored). Credits are inserted idempotently (re-uploading the same sha256
or overlapping files adds nothing); debits are skipped. The response reports
new/duplicate/skipped counts and `covered_through`.

**Email inbox.** With the `IMAP_*` env set, `backend/app/api/bank/inbox.py` fetches
the accountant's emailed `.csv` from allow-listed, DMARC/DKIM-authenticated senders
hourly (and on `POST /admin/bank-statements/check-inbox`) through the same
`import_statement` (system actor, no uploader). Each message is recorded once in
`bank_mail_fetches` as received/imported/rejected with a reason code. Each import is
audited with counts only, and admins are notified when rows join the review queue.

**Review queue** (`/admin/bank-transactions`, `backend/app/api/bank/review.py`).
Credits become payments only here. An admin can:

- **Confirm** a credit: all-or-nothing split across households, sum equals the row.
  Creates a `transfer` payment owned by whoever held the plot on the operation date;
  rejected on or before the household's `opening_balances.as_of`.
- **Link** it to an existing manual transfer (same amount, within 5 days).
- **Dismiss** it.

A credit's state is derived, not stored: live linked payment = confirmed,
`dismissed_at` = dismissed, else queued. Each action locks the row, and a repeat
returns 409 `bankTransactionResolved`. Voiding one payment of a confirmed credit
voids its siblings, so the credit returns to the queue. Payer name and purpose never
reach `Payment.note` or the audit log.

**Suggestions** (`backend/app/api/bank/matching`) are deterministic, computed on
read, no LLM, never from payer tax ID or IBAN:

1. `STR-<household id>` references in the purpose (several for a split);
2. else a single fuzzy payer-surname match against active household names;
3. else none.

A suggestion only pre-fills the confirm dialog with its reason. The Pay sheet's
purpose carries only the `STR-<id>` of the plot being paid, i.e. the current
plot (or, with no plot left, the gave-up plots that owe), so the amount and the
reference agree (`frontend/src/shared/utils/paymentPurpose.ts` mirrors `household_reference`).

**Coverage.** `GET /billing/bank-coverage` reports the max `covered_through` over
imported files and `awaiting_statement` (true when none was ever imported or the
newest is more than 21 days old, since statements arrive about days 1–6 and ~17).
Admins also get `last_imported_at`. The dashboard and the admin Bank tab show
"payments included up to DD.MM" or an awaiting notice (`BankCoverageNotice`).

## Shortfall notices

Code: `backend/app/api/billing/shortfall.py`.

- Each *app-closed* period (`closed_by_user_id` set; backfilled periods have none)
  is due on the 20th after the month following it (or the next 20th after a late
  close).
- The window is the newest such period whose due date max `covered_through` has
  reached, provided no queued credit dated on or before that date remains. Closing a
  later period therefore does not hide an earlier one.
- `notify_shortfall` runs after each import, close, and queue confirm/link/dismiss.
  It tells each owner who still owes their overdue amount (balance minus unpaid later
  periods) once per (user, period) via `NotificationLog`. Overpaid owners get
  nothing; indebted ownerless households go to admins.
- `GET /billing/shortfall` drives the dashboard's persistent `ShortfallNotice` while
  the household owes.

## Reminders

Deadline push reminders go out on days 1 and 5 at each user's chosen Kyiv hour
(`User.reminder_hour`, default 9, set via `PATCH /auth/preferences`). Users with no
push subscription get the reminder by email (Brevo) instead. Scheduler details are
in [deployment.md](deployment.md#push-reminders).

## Imports

The spreadsheet import (`backend/scripts/import_meter_history.py`) writes the
reading plus a closed period and a charge with the sheet's exact amount, never
recomputed from rates, and refuses the current period.
