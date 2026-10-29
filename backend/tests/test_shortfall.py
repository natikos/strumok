"""Shortfall notice and notification (issue #256).

Spec: a window opens only for periods the app closed (not spreadsheet
backfills); it is due on the 20th after the period (or after a late close);
nothing is said until a statement covers the due date and no credit dated on
or before it is still unreviewed; then each owner who owes hears once.
"""

import json
from datetime import date, datetime
from decimal import Decimal
from unittest.mock import patch

import pytest
from sqlmodel import Session, select

from app.core.bank_queue import has_queued_through
from app.api.billing.shortfall import ShortfallWindow, latest_window, settled_window
from app.api.push.billing_notifications import notify_shortfall
from app.api.push.service import SendOutcome
from app.db.models import (
    BankStatementFile,
    BankTransaction,
    BillingPeriod,
    HouseholdCharge,
    LanguageCode,
    NotificationLog,
    OpeningBalance,
    Payment,
)
from tests.factories import (
    authenticate,
    make_electricity_rate,
    make_household,
    make_meter_reading,
    make_push_subscription,
    make_user,
)

MOD = "app.api.push.billing_notifications"
D = Decimal
DUE = date(2025, 4, 20)


@pytest.fixture
def send_one():
    with patch(f"{MOD}.send_one", return_value=SendOutcome.SENT) as m:
        yield m


@pytest.fixture(autouse=True)
def send_email():
    with patch(f"{MOD}.send_email") as m:
        yield m


def _closed(
    session: Session,
    period: str,
    closed_at: datetime | None,
    by_app: bool = True,
) -> None:
    closer = make_user(session) if by_app else None
    session.add(
        BillingPeriod(
            period=period,
            status="closed",
            closed_at=closed_at,
            closed_by_user_id=closer.id if closer else None,
        )
    )
    session.flush()


def _open_window(session: Session) -> None:
    """Period 2025-03 closed in April: due 2025-04-20."""
    _closed(session, "2025-03", datetime(2025, 4, 10, 9, 0))


def _file(session: Session, covered: date, sha: str = "a" * 64) -> BankStatementFile:
    f = BankStatementFile(
        sha256=sha,
        original_filename="s.csv",
        encoding="utf-8",
        account_iban="UA0",
        first_operation_date=covered,
        last_operation_date=covered,
        covered_through=covered,
        rows_total=1,
        credits_new=1,
        credits_duplicate=0,
        debits_skipped=0,
    )
    session.add(f)
    session.flush()
    return f


def _credit(session: Session, day: date, doc: str = "d1") -> BankTransaction:
    f = session.exec(select(BankStatementFile)).first() or _file(session, day)
    tx = BankTransaction(
        document_number=doc,
        operation_date=day,
        amount_uah=D("10.00"),
        payer_iban="UA1",
        payer_name="X",
        purpose="p",
        first_file_id=f.id,
    )
    session.add(tx)
    session.flush()
    return tx


def _owes(session: Session, household_id: int, owner_id: int | None, amount: str):
    session.add(
        OpeningBalance(
            household_id=household_id,
            owner_user_id=owner_id,
            amount_uah=D(amount),
            as_of=date(2025, 1, 1),
        )
    )
    session.flush()


def _subscribed_user(session: Session, **kw):
    user = make_user(session, **kw)
    user.language = LanguageCode.EN
    make_push_subscription(session, user_id=user.id)
    return user


def _body(call) -> str:
    return json.loads(call.args[1])["body"]


def _ready(session: Session, covered: date = DUE) -> None:
    _open_window(session)
    _file(session, covered)


class TestLatestWindow:
    def test_backfilled_periods_open_no_window(self, session: Session) -> None:
        _closed(session, "2025-03", datetime(2025, 4, 10), by_app=False)
        assert latest_window(session) is None

    def test_no_periods_open_no_window(self, session: Session) -> None:
        assert latest_window(session) is None

    def test_open_period_opens_no_window(self, session: Session) -> None:
        session.add(BillingPeriod(period="2025-03", status="open"))
        session.flush()
        assert latest_window(session) is None

    def test_due_on_20th_of_month_after_period(self, session: Session) -> None:
        _closed(session, "2025-03", datetime(2025, 4, 10, 9, 0))
        assert latest_window(session) == ShortfallWindow("2025-03", DUE)

    def test_late_close_after_the_20th_is_due_next_month(
        self, session: Session
    ) -> None:
        _closed(session, "2025-03", datetime(2025, 4, 25, 9, 0))
        assert latest_window(session) == ShortfallWindow("2025-03", date(2025, 5, 20))

    def test_december_period_rolls_into_next_year(self, session: Session) -> None:
        _closed(session, "2025-12", datetime(2026, 1, 5, 9, 0))
        assert latest_window(session) == ShortfallWindow("2025-12", date(2026, 1, 20))

    def test_december_period_closed_late_in_january_is_due_in_february(
        self, session: Session
    ) -> None:
        _closed(session, "2025-12", datetime(2026, 1, 28, 9, 0))
        assert latest_window(session) == ShortfallWindow("2025-12", date(2026, 2, 20))

    def test_close_late_evening_utc_counts_as_next_day_in_kyiv(
        self, session: Session
    ) -> None:
        # 21:30 UTC on Apr 20 is Apr 21 00:30 in Kyiv (UTC+3): after the 20th.
        _closed(session, "2025-03", datetime(2025, 4, 20, 21, 30))
        assert latest_window(session) == ShortfallWindow("2025-03", date(2025, 5, 20))

    def test_latest_app_closed_period_wins_over_unsorted_others(
        self, session: Session
    ) -> None:
        _closed(session, "2025-02", datetime(2025, 3, 10))
        _closed(session, "2025-04", datetime(2025, 5, 10))
        _closed(session, "2025-05", datetime(2025, 6, 10), by_app=False)
        _closed(session, "2025-03", datetime(2025, 4, 10))
        assert latest_window(session) == ShortfallWindow("2025-04", date(2025, 5, 20))


class TestHasQueuedThrough:
    def test_credit_on_the_due_date_is_queued_through_it(
        self, session: Session
    ) -> None:
        _credit(session, DUE)
        assert has_queued_through(session, DUE)

    def test_credit_after_the_due_date_does_not_count(self, session: Session) -> None:
        _credit(session, date(2025, 4, 21))
        assert not has_queued_through(session, DUE)

    def test_dismissed_credit_does_not_count(self, session: Session) -> None:
        _credit(session, date(2025, 4, 1)).dismissed_at = datetime(2025, 4, 2)
        session.flush()
        assert not has_queued_through(session, DUE)

    def test_confirmed_credit_does_not_count_but_voided_link_does(
        self, session: Session
    ) -> None:
        tx = _credit(session, date(2025, 4, 1))
        h = make_household(session)
        pay = Payment(
            household_id=h.id,
            amount_uah=D("10.00"),
            paid_on=date(2025, 4, 1),
            method="transfer",
            bank_transaction_id=tx.id,
        )
        session.add(pay)
        session.flush()
        assert not has_queued_through(session, DUE)
        pay.voided_at = datetime(2025, 4, 3)
        session.flush()
        assert has_queued_through(session, DUE)


class TestNotifyShortfall:
    def test_nothing_without_window(self, session: Session, send_one) -> None:
        _file(session, DUE)
        user = _subscribed_user(session)
        _owes(session, make_household(session, user_id=user.id).id, user.id, "50.00")
        assert notify_shortfall(session=session) == 0
        send_one.assert_not_called()

    def test_nothing_without_any_statement(self, session: Session, send_one) -> None:
        _open_window(session)
        user = _subscribed_user(session)
        _owes(session, make_household(session, user_id=user.id).id, user.id, "50.00")
        assert notify_shortfall(session=session) == 0
        send_one.assert_not_called()

    def test_nothing_until_statement_covers_due_date(
        self, session: Session, send_one
    ) -> None:
        _ready(session, covered=date(2025, 4, 19))
        user = _subscribed_user(session)
        _owes(session, make_household(session, user_id=user.id).id, user.id, "50.00")
        assert notify_shortfall(session=session) == 0
        send_one.assert_not_called()

    def test_sends_once_covered_and_max_coverage_counts(
        self, session: Session, send_one
    ) -> None:
        _open_window(session)
        _file(session, date(2025, 4, 25), "b" * 64)
        _file(session, date(2025, 4, 5), "c" * 64)
        user = _subscribed_user(session)
        _owes(session, make_household(session, user_id=user.id).id, user.id, "50.00")
        assert notify_shortfall(session=session) == 1

    def test_queued_credit_on_or_before_due_date_suppresses(
        self, session: Session, send_one
    ) -> None:
        _ready(session)
        _credit(session, DUE)
        user = _subscribed_user(session)
        _owes(session, make_household(session, user_id=user.id).id, user.id, "50.00")
        assert notify_shortfall(session=session) == 0
        send_one.assert_not_called()

    def test_queued_credit_after_due_date_does_not_suppress(
        self, session: Session, send_one
    ) -> None:
        _ready(session, covered=date(2025, 4, 25))
        _credit(session, date(2025, 4, 21))
        user = _subscribed_user(session)
        _owes(session, make_household(session, user_id=user.id).id, user.id, "50.00")
        assert notify_shortfall(session=session) == 1

    def test_dismissed_credit_does_not_suppress(
        self, session: Session, send_one
    ) -> None:
        _ready(session)
        _credit(session, date(2025, 4, 1)).dismissed_at = datetime(2025, 4, 2)
        user = _subscribed_user(session)
        _owes(session, make_household(session, user_id=user.id).id, user.id, "50.00")
        assert notify_shortfall(session=session) == 1

    def test_owner_gets_balance_once_across_repeated_calls(
        self, session: Session, send_one
    ) -> None:
        _ready(session)
        user = _subscribed_user(session)
        _owes(session, make_household(session, user_id=user.id).id, user.id, "123.45")

        first = notify_shortfall(session=session)
        second = notify_shortfall(session=session)

        assert (first, second) == (1, 0)
        assert send_one.call_count == 1
        assert "123.45" in _body(send_one.call_args)
        logs = session.exec(select(NotificationLog)).all()
        assert [(log.period, log.variant) for log in logs] == [("2025-03", "shortfall")]

    def test_zero_and_overpaid_households_get_nothing(
        self, session: Session, send_one
    ) -> None:
        _ready(session)
        zero = _subscribed_user(session)
        over = _subscribed_user(session)
        _owes(
            session,
            make_household(session, name="Z", user_id=zero.id).id,
            zero.id,
            "0.00",
        )
        _owes(
            session,
            make_household(session, name="O", user_id=over.id).id,
            over.id,
            "-40.00",
        )
        assert notify_shortfall(session=session) == 0
        send_one.assert_not_called()

    def test_multi_household_owner_gets_one_summed_total_ignoring_credit_plots(
        self, session: Session, send_one
    ) -> None:
        _ready(session)
        user = _subscribed_user(session)
        _owes(
            session,
            make_household(session, name="A", user_id=user.id).id,
            user.id,
            "0.10",
        )
        _owes(
            session,
            make_household(session, name="B", user_id=user.id).id,
            user.id,
            "0.20",
        )
        _owes(
            session,
            make_household(session, name="C", user_id=user.id).id,
            user.id,
            "100.01",
        )
        _owes(
            session,
            make_household(session, name="D", user_id=user.id).id,
            user.id,
            "-500.00",
        )

        assert notify_shortfall(session=session) == 1
        assert "100.31" in _body(send_one.call_args)

    def test_inactive_household_debt_is_not_reported(
        self, session: Session, send_one
    ) -> None:
        _ready(session)
        user = _subscribed_user(session)
        _owes(
            session,
            make_household(session, user_id=user.id, is_active=False).id,
            user.id,
            "50.00",
        )
        assert notify_shortfall(session=session) == 0

    def test_ownerless_indebted_household_is_reported_to_admins_only(
        self, session: Session, send_one
    ) -> None:
        _ready(session)
        admin = _subscribed_user(session, is_admin=True)
        resident = _subscribed_user(session)
        _owes(session, make_household(session, name="Orphan").id, None, "75.00")
        _owes(
            session,
            make_household(session, name="Paid", user_id=resident.id).id,
            resident.id,
            "0.00",
        )

        assert notify_shortfall(session=session) == 1
        (call,) = send_one.call_args_list
        assert call.args[0].user_id == admin.id
        assert "Orphan" in _body(call)
        assert "Paid" not in _body(call)
        variants = {log.variant for log in session.exec(select(NotificationLog))}
        assert variants == {"shortfallOwnerless"}


class TestEndpoint:
    def test_inactive_without_window(self, client, session: Session) -> None:
        user = make_user(session)
        _owes(session, make_household(session, user_id=user.id).id, user.id, "50.00")
        authenticate(client, user)
        assert client.get("/billing/shortfall").json()["active"] is False

    def test_active_with_due_date_and_exact_owed(
        self, client, session: Session
    ) -> None:
        _ready(session)
        user = make_user(session)
        _owes(session, make_household(session, user_id=user.id).id, user.id, "100.30")
        authenticate(client, user)
        body = client.get("/billing/shortfall").json()
        assert body["active"] is True
        assert body["due_date"] == "2025-04-20"
        assert D(str(body["owed_uah"])) == D("100.30")

    def test_inactive_when_nothing_owed(self, client, session: Session) -> None:
        _ready(session)
        user = make_user(session)
        _owes(session, make_household(session, user_id=user.id).id, user.id, "-5.00")
        authenticate(client, user)
        assert client.get("/billing/shortfall").json()["active"] is False

    def test_inactive_while_credit_awaits_review(
        self, client, session: Session
    ) -> None:
        _ready(session)
        _credit(session, date(2025, 4, 2))
        user = make_user(session)
        _owes(session, make_household(session, user_id=user.id).id, user.id, "50.00")
        authenticate(client, user)
        assert client.get("/billing/shortfall").json()["active"] is False

    def test_reports_selected_household_not_the_sum(
        self, client, session: Session
    ) -> None:
        _ready(session)
        user = make_user(session)
        a = make_household(session, name="A", user_id=user.id)
        b = make_household(session, name="B", user_id=user.id)
        _owes(session, a.id, user.id, "10.00")
        _owes(session, b.id, user.id, "20.00")
        authenticate(client, user)
        body = client.get("/billing/shortfall", params={"household_id": b.id}).json()
        assert D(str(body["owed_uah"])) == D("20.00")

    def test_other_users_household_is_forbidden(self, client, session: Session) -> None:
        _ready(session)
        me = make_user(session)
        make_household(session, name="Mine", user_id=me.id)
        other = make_user(session)
        theirs = make_household(session, name="Theirs", user_id=other.id)
        _owes(session, theirs.id, other.id, "50.00")
        authenticate(client, me)
        res = client.get("/billing/shortfall", params={"household_id": theirs.id})
        assert res.status_code == 403
        assert res.json()["detail"] == "householdNotAccessible"

    def test_no_household_is_404_and_no_cookie_is_401(
        self, client, session: Session
    ) -> None:
        assert client.get("/billing/shortfall").status_code == 401
        authenticate(client, make_user(session))
        res = client.get("/billing/shortfall")
        assert (res.status_code, res.json()["detail"]) == (404, "noHouseholdMembership")


class TestTriggers:
    def test_statement_import_notifies_owner(
        self, client, session: Session, send_one
    ) -> None:
        from tests.test_bank_import import OWN, _admin, _csv, _row, _upload

        _admin(client, session)
        _open_window(session)
        user = _subscribed_user(session)
        _owes(session, make_household(session, user_id=user.id).id, user.id, "42.00")
        # Statement row dated on the due date is imported and queued; a later
        # one after it keeps the queue-before-due empty only if dismissed, so
        # use a credit after the due date.
        res = _upload(client, _csv(_row("1.", "25.04.2025")))
        assert res.status_code == 200, res.text
        assert OWN
        assert send_one.call_count == 1
        assert "42.00" in _body(send_one.call_args)

    def test_import_failure_in_notification_does_not_fail_upload(
        self, client, session: Session
    ) -> None:
        from tests.test_bank_import import _admin, _csv, _row, _upload

        _admin(client, session)
        with patch("app.api.bank.routes.notify_shortfall", side_effect=RuntimeError):
            assert _upload(client, _csv(_row())).status_code == 200

    def test_closing_a_period_triggers_notification_hook(
        self, client, session: Session
    ) -> None:
        admin = make_user(session, is_admin=True)
        authenticate(client, admin)
        make_electricity_rate(session, day_rate_uah="2", night_rate_uah="1")
        h = make_household(session, user_id=make_user(session).id)
        for period, day, night in (("2024-01", "100", "50"), ("2024-02", "130", "60")):
            make_meter_reading(
                session,
                household_id=h.id,
                period=period,
                day_meter_value=day,
                night_meter_value=night,
            )
        with patch("app.api.admin.routes.notify_shortfall") as hook:
            client.put(
                "/admin/periods/2024-02/bill",
                json={
                    "day_kwh": "30",
                    "night_kwh": "10",
                    "total_uah": "70.00",
                    "confirm": True,
                },
            )
            res = client.post(
                "/admin/periods/2024-02/close",
                json={"confirm": True, "acknowledge_flags": False},
            )
        assert res.status_code == 200, res.text
        hook.assert_called_once()


def _charge(
    session: Session, period: str, household_id: int, owner_id: int, amount: str
) -> None:
    session.add(
        HouseholdCharge(
            period=period,
            household_id=household_id,
            owner_user_id=owner_id,
            day_usage_kwh=D("0"),
            night_usage_kwh=D("0"),
            tariff_uah=D(amount),
            total_uah=D(amount),
        )
    )
    session.flush()


def _paid(session: Session, household_id: int, owner_id: int, amount: str) -> None:
    session.add(
        Payment(
            household_id=household_id,
            owner_user_id=owner_id,
            amount_uah=D(amount),
            paid_on=date(2025, 4, 1),
            method="transfer",
        )
    )
    session.flush()


def _two_closed_periods(session: Session) -> None:
    """P1 2025-02 closed in March (due 03-20); P2 2025-03 closed in April (due 04-20)."""
    _closed(session, "2025-02", datetime(2025, 3, 10, 9, 0))
    _closed(session, "2025-03", datetime(2025, 4, 10, 9, 0))


class TestSettledWindowWithTwoClosedPeriods:
    def test_older_period_stays_active_while_newer_due_date_is_uncovered(
        self, client, session: Session
    ) -> None:
        _two_closed_periods(session)
        _file(session, date(2025, 4, 1))
        user = make_user(session)
        _owes(session, make_household(session, user_id=user.id).id, user.id, "50.00")
        authenticate(client, user)

        assert settled_window(session) == ShortfallWindow("2025-02", date(2025, 3, 20))
        body = client.get("/billing/shortfall").json()
        assert body["active"] is True
        assert body["due_date"] == "2025-03-20"

    def test_window_moves_to_newer_period_once_its_due_date_is_covered(
        self, session: Session
    ) -> None:
        _two_closed_periods(session)
        _file(session, date(2025, 4, 20))
        assert settled_window(session) == ShortfallWindow("2025-03", DUE)

    def test_nothing_while_no_due_date_is_covered(self, session: Session) -> None:
        _two_closed_periods(session)
        _file(session, date(2025, 3, 19))
        assert settled_window(session) is None

    def test_queued_credit_before_older_due_date_blocks_it(
        self, session: Session
    ) -> None:
        _two_closed_periods(session)
        _file(session, date(2025, 4, 1))
        _credit(session, date(2025, 3, 5))
        assert settled_window(session) is None


class TestOverdueOnlyAmount:
    def _setup(self, session: Session):
        _two_closed_periods(session)
        _file(session, date(2025, 3, 25))  # covers P1's due date only
        user = _subscribed_user(session)
        h = make_household(session, user_id=user.id)
        return user, h

    def test_only_overdue_period_is_reported_when_later_one_is_not_yet_due(
        self, client, session: Session, send_one
    ) -> None:
        user, h = self._setup(session)
        _charge(session, "2025-02", h.id, user.id, "100.10")
        _charge(session, "2025-03", h.id, user.id, "40.20")
        authenticate(client, user)

        assert notify_shortfall(session=session) == 1
        assert "100.10" in _body(send_one.call_args)
        assert "140.30" not in _body(send_one.call_args)
        body = client.get("/billing/shortfall").json()
        assert D(str(body["owed_uah"])) == D("100.10")

    def test_partial_payment_settles_oldest_period_first(
        self, client, session: Session
    ) -> None:
        user, h = self._setup(session)
        _charge(session, "2025-02", h.id, user.id, "100.10")
        _charge(session, "2025-03", h.id, user.id, "40.20")
        _paid(session, h.id, user.id, "30.05")
        authenticate(client, user)
        body = client.get("/billing/shortfall").json()
        assert D(str(body["owed_uah"])) == D("70.05")

    def test_payment_beyond_overdue_part_leaves_nothing_overdue(
        self, client, session: Session, send_one
    ) -> None:
        user, h = self._setup(session)
        _charge(session, "2025-02", h.id, user.id, "100.10")
        _charge(session, "2025-03", h.id, user.id, "40.20")
        _paid(session, h.id, user.id, "120.00")  # spills 19.90 into P2
        authenticate(client, user)
        assert client.get("/billing/shortfall").json()["active"] is False
        assert notify_shortfall(session=session) == 0
        send_one.assert_not_called()

    def test_household_owing_only_later_period_gets_nothing(
        self, client, session: Session, send_one
    ) -> None:
        user, h = self._setup(session)
        _charge(session, "2025-03", h.id, user.id, "40.20")
        authenticate(client, user)
        assert client.get("/billing/shortfall").json()["active"] is False
        assert notify_shortfall(session=session) == 0
        send_one.assert_not_called()

    def test_opening_balance_counts_as_overdue_alongside_later_debt(
        self, client, session: Session
    ) -> None:
        user, h = self._setup(session)
        _owes(session, h.id, user.id, "10.00")
        _charge(session, "2025-03", h.id, user.id, "40.20")
        authenticate(client, user)
        body = client.get("/billing/shortfall").json()
        assert D(str(body["owed_uah"])) == D("10.00")


class TestQueueClearingTriggersNotification:
    def test_import_with_queued_credits_is_silent_until_last_is_dismissed(
        self, client, session: Session, send_one
    ) -> None:
        from tests.test_bank_import import _admin, _csv, _row, _upload

        _admin(client, session)
        _open_window(session)
        user = _subscribed_user(session)
        _owes(session, make_household(session, user_id=user.id).id, user.id, "42.00")

        res = _upload(client, _csv(_row("1.", "05.04.2025"), _row("2.", "20.04.2025")))
        assert res.status_code == 200, res.text
        send_one.assert_not_called()
        first, second = session.exec(
            select(BankTransaction).order_by(BankTransaction.id)  # type: ignore[arg-type]
        ).all()

        assert (
            client.post(f"/admin/bank-transactions/{first.id}/dismiss").status_code
            == 204
        )
        send_one.assert_not_called()

        assert (
            client.post(f"/admin/bank-transactions/{second.id}/dismiss").status_code
            == 204
        )
        assert send_one.call_count == 1
        assert "42.00" in _body(send_one.call_args)

        # Further review actions never notify the same owner twice.
        _credit(session, date(2025, 4, 25), "late")
        late = session.exec(
            select(BankTransaction).where(BankTransaction.document_number == "late")
        ).one()
        client.post(f"/admin/bank-transactions/{late.id}/dismiss")
        assert send_one.call_count == 1

    def test_confirm_route_triggers_hook(self, client, session: Session) -> None:
        from tests.test_bank_review import _admin, _confirm, _tx

        _admin(client, session)
        h = make_household(session)
        tx = _tx(session, day=date(2025, 5, 15))
        with patch("app.api.bank.routes.notify_shortfall") as hook:
            assert _confirm(client, tx, (h.id, "500.00")).status_code == 200
        hook.assert_called_once()

    def test_link_route_triggers_hook(self, client, session: Session) -> None:
        from tests.test_bank_review import BASE, _admin, _tx

        admin = _admin(client, session)
        h = make_household(session)
        tx = _tx(session, day=date(2025, 5, 15))
        pay = Payment(
            household_id=h.id,
            amount_uah=D("500.00"),
            paid_on=date(2025, 5, 12),
            method="transfer",
            recorded_by_user_id=admin.id,
        )
        session.add(pay)
        session.flush()
        with patch("app.api.bank.routes.notify_shortfall") as hook:
            res = client.post(f"{BASE}/{tx.id}/link", json={"payment_id": pay.id})
        assert res.status_code == 204
        hook.assert_called_once()

    def test_dismiss_route_triggers_hook_and_failure_does_not_fail_it(
        self, client, session: Session
    ) -> None:
        from tests.test_bank_review import BASE, _admin, _tx

        _admin(client, session)
        tx = _tx(session)
        with patch(
            "app.api.bank.routes.notify_shortfall", side_effect=RuntimeError
        ) as hook:
            assert client.post(f"{BASE}/{tx.id}/dismiss").status_code == 204
        hook.assert_called_once()

    def test_rejected_review_action_does_not_trigger_hook(
        self, client, session: Session
    ) -> None:
        from tests.test_bank_review import BASE, _admin

        _admin(client, session)
        with patch("app.api.bank.routes.notify_shortfall") as hook:
            assert client.post(f"{BASE}/999999/dismiss").status_code == 404
        hook.assert_not_called()
