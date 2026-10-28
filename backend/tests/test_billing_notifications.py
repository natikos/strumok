"""Bill-ready, correction and missing-readings notifications (issue #179).

Delivery is mocked at `send_one` / `send_email`; nothing touches the network.
The things that matter to residents: one notification per event no matter how
often the trigger fires, no phantom "+0.00" corrections, and a failed delivery
must not burn the claim (or the user is never told).
"""

import json
from decimal import Decimal
from unittest.mock import patch

import pytest
from sqlmodel import Session, select

from app.api.push.billing_notifications import (
    notify_bill_ready,
    notify_corrections,
    notify_missing_readings,
)
from app.api.push.service import SendOutcome
from app.core.email import EmailSendError
from app.db.models import (
    BillingPeriod,
    HouseholdCharge,
    LanguageCode,
    NotificationLog,
)
from tests.factories import (
    authenticate,
    make_electricity_rate,
    make_household,
    make_meter_reading,
    make_push_subscription,
    make_user,
)

D = Decimal
PERIOD = "2024-02"
MOD = "app.api.push.billing_notifications"


@pytest.fixture
def send_one():
    with patch(f"{MOD}.send_one", return_value=SendOutcome.SENT) as m:
        yield m


@pytest.fixture
def send_email():
    with patch(f"{MOD}.send_email") as m:
        yield m


def _charge(
    session: Session, household_id: int, owner_id: int | None, total: str, **kw
) -> None:
    if session.get(BillingPeriod, PERIOD) is None:
        session.add(BillingPeriod(period=PERIOD, status="closed"))
        session.flush()
    session.add(
        HouseholdCharge(
            period=PERIOD,
            household_id=household_id,
            owner_user_id=owner_id,
            day_usage_kwh=D("1"),
            night_usage_kwh=D("1"),
            tariff_uah=D(total),
            total_uah=D(total),
            **kw,
        )
    )
    session.flush()


def _payload(call) -> dict:
    return json.loads(call.args[1])


def _logs(session: Session) -> list[NotificationLog]:
    return list(session.exec(select(NotificationLog)).all())


class TestBillReady:
    def test_sends_once_per_resident_even_when_called_twice(
        self, session: Session, send_one
    ) -> None:
        user = make_user(session)
        make_push_subscription(session, user_id=user.id)
        _charge(session, make_household(session, user_id=user.id).id, user.id, "10.10")

        first = notify_bill_ready(session=session, period=PERIOD)
        second = notify_bill_ready(session=session, period=PERIOD)

        assert (first, second) == (1, 0)
        assert send_one.call_count == 1

    def test_sums_a_residents_households_into_one_message(
        self, session: Session, send_one
    ) -> None:
        user = make_user(session)
        make_push_subscription(session, user_id=user.id)
        _charge(
            session,
            make_household(session, name="A", user_id=user.id).id,
            user.id,
            "0.10",
        )
        _charge(
            session,
            make_household(session, name="B", user_id=user.id).id,
            user.id,
            "0.20",
        )
        _charge(
            session,
            make_household(session, name="C", user_id=user.id).id,
            user.id,
            "100.01",
        )

        notify_bill_ready(session=session, period=PERIOD)

        assert send_one.call_count == 1
        assert "100.31" in _payload(send_one.call_args)["body"]

    def test_estimated_flag_is_mentioned_only_for_residents_with_an_estimate(
        self, session: Session, send_one
    ) -> None:
        est = make_user(session)
        exact = make_user(session)
        for u in (est, exact):
            u.language = LanguageCode.EN
            make_push_subscription(session, user_id=u.id)
        _charge(
            session,
            make_household(session, user_id=est.id).id,
            est.id,
            "5.00",
            is_estimated=True,
        )
        _charge(session, make_household(session, user_id=exact.id).id, exact.id, "5.00")

        notify_bill_ready(session=session, period=PERIOD)

        by_user = {
            c.args[0].user_id: _payload(c)["body"] for c in send_one.call_args_list
        }
        assert "estimate" in by_user[est.id]
        assert "estimate" not in by_user[exact.id]

    def test_unowned_household_charge_notifies_nobody(
        self, session: Session, send_one, send_email
    ) -> None:
        _charge(session, make_household(session).id, None, "5.00")

        assert notify_bill_ready(session=session, period=PERIOD) == 0
        send_one.assert_not_called()
        send_email.assert_not_called()


class TestCorrections:
    def test_zero_net_delta_is_skipped_and_nonzero_is_signed(
        self, session: Session, send_one
    ) -> None:
        zero = make_user(session)
        down = make_user(session)
        for u in (zero, down):
            u.language = LanguageCode.EN
            make_push_subscription(session, user_id=u.id)

        sent = notify_corrections(
            session=session,
            restatement_id=7,
            period=PERIOD,
            deltas={zero.id: D("0.00"), down.id: D("-3.50")},
        )

        assert sent == 1
        (call,) = send_one.call_args_list
        assert call.args[0].user_id == down.id
        assert "-3.50" in _payload(call)["body"]
        assert [log.user_id for log in _logs(session)] == [down.id]

    def test_separate_restatements_each_notify_the_same_resident(
        self, session: Session, send_one
    ) -> None:
        user = make_user(session)
        make_push_subscription(session, user_id=user.id)
        for rid in (1, 2, 1):
            notify_corrections(
                session=session,
                restatement_id=rid,
                period=PERIOD,
                deltas={user.id: D("1.00")},
            )

        assert send_one.call_count == 2


class TestMissingReadings:
    def test_admins_get_only_active_households_without_a_reading_sorted(
        self, session: Session, send_one
    ) -> None:
        admin = make_user(session, is_admin=True)
        admin.language = LanguageCode.EN
        make_push_subscription(session, user_id=admin.id)
        resident = make_user(session)
        make_push_subscription(session, user_id=resident.id)
        done = make_household(session, name="Done")
        make_household(session, name="Zeta")
        make_household(session, name="Alpha")
        make_household(session, name="Retired", is_active=False)
        make_meter_reading(session, household_id=done.id, period=PERIOD)
        # a reading for another period must not count as submitted
        other = make_household(session, name="Beta")
        make_meter_reading(session, household_id=other.id, period="2024-01")

        sent = notify_missing_readings(session=session, period=PERIOD)

        assert sent == 1
        (call,) = send_one.call_args_list
        assert call.args[0].user_id == admin.id
        assert (
            _payload(call)["body"]
            == "3 households haven't submitted 2024-02: Alpha, Beta, Zeta"
        )
        assert "Done" not in _payload(call)["body"]
        assert "Retired" not in _payload(call)["body"]

    def test_sends_once_when_run_twice(self, session: Session, send_one) -> None:
        admin = make_user(session, is_admin=True)
        make_push_subscription(session, user_id=admin.id)
        make_household(session, name="Alpha")

        assert notify_missing_readings(session=session, period=PERIOD) == 1
        assert notify_missing_readings(session=session, period=PERIOD) == 0
        assert send_one.call_count == 1

    def test_nothing_is_sent_when_every_household_submitted(
        self, session: Session, send_one, send_email
    ) -> None:
        make_user(session, is_admin=True)
        h = make_household(session)
        make_meter_reading(session, household_id=h.id, period=PERIOD)

        assert notify_missing_readings(session=session, period=PERIOD) == 0
        send_one.assert_not_called()
        send_email.assert_not_called()


class TestDeliveryFallbackAndRetry:
    def test_user_without_push_subscription_is_emailed(
        self, session: Session, send_one, send_email
    ) -> None:
        user = make_user(session, email="res@example.com")
        _charge(session, make_household(session, user_id=user.id).id, user.id, "9.99")

        assert notify_bill_ready(session=session, period=PERIOD) == 1
        send_one.assert_not_called()
        kwargs = send_email.call_args.kwargs
        assert kwargs["to_email"] == "res@example.com"
        assert "9.99" in kwargs["html_content"]

    def test_email_is_not_sent_when_push_succeeded(
        self, session: Session, send_one, send_email
    ) -> None:
        user = make_user(session)
        make_push_subscription(session, user_id=user.id)
        _charge(session, make_household(session, user_id=user.id).id, user.id, "9.99")

        notify_bill_ready(session=session, period=PERIOD)

        send_email.assert_not_called()

    def test_claim_is_released_when_push_fails_so_a_retry_notifies(
        self, session: Session, send_one
    ) -> None:
        user = make_user(session)
        make_push_subscription(session, user_id=user.id)
        _charge(session, make_household(session, user_id=user.id).id, user.id, "9.99")

        send_one.return_value = SendOutcome.FAILED
        assert notify_bill_ready(session=session, period=PERIOD) == 0
        assert _logs(session) == []

        send_one.return_value = SendOutcome.SENT
        assert notify_bill_ready(session=session, period=PERIOD) == 1
        assert len(_logs(session)) == 1

    def test_claim_is_released_when_email_fallback_fails(
        self, session: Session, send_email
    ) -> None:
        user = make_user(session)
        _charge(session, make_household(session, user_id=user.id).id, user.id, "9.99")

        send_email.side_effect = EmailSendError("down")
        assert notify_bill_ready(session=session, period=PERIOD) == 0
        assert _logs(session) == []

        send_email.side_effect = None
        assert notify_bill_ready(session=session, period=PERIOD) == 1

    def test_one_failed_user_does_not_release_another_users_claim(
        self, session: Session
    ) -> None:
        ok = make_user(session)
        bad = make_user(session)
        make_push_subscription(session, user_id=ok.id)
        make_push_subscription(session, user_id=bad.id)
        _charge(
            session, make_household(session, name="A", user_id=ok.id).id, ok.id, "1.00"
        )
        _charge(
            session,
            make_household(session, name="B", user_id=bad.id).id,
            bad.id,
            "1.00",
        )

        def fake(sub, *_a, **_k):
            return SendOutcome.SENT if sub.user_id == ok.id else SendOutcome.FAILED

        with patch(f"{MOD}.send_one", side_effect=fake):
            assert notify_bill_ready(session=session, period=PERIOD) == 1

        assert [log.user_id for log in _logs(session)] == [ok.id]


class TestClosePeriodRouteNotifies:
    def _setup(self, client, session: Session):
        authenticate(client, make_user(session, is_admin=True))
        make_electricity_rate(session, day_rate_uah="2", night_rate_uah="1")
        owner = make_user(session)
        make_push_subscription(session, user_id=owner.id)
        h = make_household(session, user_id=owner.id)
        make_meter_reading(
            session,
            household_id=h.id,
            period="2024-01",
            day_meter_value="100",
            night_meter_value="50",
        )
        make_meter_reading(
            session,
            household_id=h.id,
            period=PERIOD,
            day_meter_value="130",
            night_meter_value="60",
        )
        response = client.put(
            f"/admin/periods/{PERIOD}/bill",
            json={
                "day_kwh": "30",
                "night_kwh": "10",
                "total_uah": "70.00",
                "confirm": True,
            },
        )
        assert response.status_code == 200, response.text
        return owner

    def test_successful_close_notifies_the_owner_once(
        self, client, session: Session, send_one
    ) -> None:
        owner = self._setup(client, session)

        response = client.post(
            f"/admin/periods/{PERIOD}/close",
            json={"confirm": True, "acknowledge_flags": False},
        )

        assert response.status_code == 200, response.text
        (call,) = send_one.call_args_list
        assert call.args[0].user_id == owner.id
        assert "70.00" in _payload(call)["body"]

    def test_failed_close_sends_nothing(
        self, client, session: Session, send_one, send_email
    ) -> None:
        authenticate(client, make_user(session, is_admin=True))
        owner = make_user(session)
        make_push_subscription(session, user_id=owner.id)
        h = make_household(session, user_id=owner.id)
        make_meter_reading(session, household_id=h.id, period=PERIOD)
        client.put(
            f"/admin/periods/{PERIOD}/bill",
            json={
                "day_kwh": "0",
                "night_kwh": "0",
                "total_uah": "0.00",
                "confirm": True,
            },
        )

        response = client.post(
            f"/admin/periods/{PERIOD}/close",
            json={"confirm": True, "acknowledge_flags": False},
        )

        assert response.status_code == 409
        assert response.json()["detail"] == "noRateConfigured"
        send_one.assert_not_called()
        send_email.assert_not_called()
        assert _logs(session) == []

    def test_second_close_attempt_does_not_renotify(
        self, client, session: Session, send_one
    ) -> None:
        self._setup(client, session)
        body = {"confirm": True, "acknowledge_flags": False}
        client.post(f"/admin/periods/{PERIOD}/close", json=body)
        again = client.post(f"/admin/periods/{PERIOD}/close", json=body)

        assert again.status_code == 409
        assert send_one.call_count == 1
