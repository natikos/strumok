"""The hourly cron tick (issue #357): `POST /internal/cron/tick`.

The tick opens its own sessions on the real engine and takes Postgres advisory
locks on separate connections, so the per-test rollback `session` fixture can't
see (or hold back) its work. These tests therefore commit their data and wipe the
touched tables afterwards. Only the network edges are replaced: web push, email,
and the IMAP fetch.
"""

import logging
from datetime import datetime
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

import pytest
from app.api.bank.inbox import InboxNotConfiguredError, InboxUnavailableError
from app.api.cron import service as cron_service
from app.api.push.service import SendOutcome
from app.core.config import settings
from app.db.engine import engine
from app.db.models import (
    Household,
    MeterReading,
    NotificationLog,
    PushSubscription,
    User,
)
from app.main import app
from pydantic import SecretStr
from sqlalchemy import text
from sqlmodel import Session, select
from starlette.testclient import TestClient
from tests.factories import make_household, make_push_subscription, make_user

SECRET = "s3cret-cron-value-0123456789"
INBOX_SECRET = "inbox-trigger-value-9876543210"
KYIV = ZoneInfo("Europe/Kyiv")
URL = "/internal/cron/tick"
CSRF = {"X-Requested-With": "cron-tick"}


def _auth(secret: str = SECRET) -> dict[str, str]:
    return {**CSRF, "X-Cron-Secret": secret}


def _kyiv(year: int, month: int, day: int, hour: int) -> datetime:
    return datetime(year, month, day, hour, 0, tzinfo=KYIV)


@pytest.fixture(autouse=True)
def _clean_db(engine):
    def wipe() -> None:
        with Session(engine) as s:
            for model in (
                NotificationLog,
                PushSubscription,
                MeterReading,
                Household,
                User,
            ):
                s.exec(model.__table__.delete())  # type: ignore[attr-defined]
            s.commit()

    wipe()
    yield
    wipe()


@pytest.fixture
def pushes(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    send = MagicMock(return_value=SendOutcome.SENT)
    monkeypatch.setattr("app.api.push.service.send_one", send)
    monkeypatch.setattr("app.api.push.billing_notifications.send_one", send)
    monkeypatch.setattr("app.api.push.service.send_email", MagicMock())
    monkeypatch.setattr("app.api.push.billing_notifications.send_email", MagicMock())
    return send


@pytest.fixture
def inbox(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    fake = MagicMock(side_effect=InboxNotConfiguredError())
    monkeypatch.setattr(cron_service, "check_inbox", fake)
    return fake


@pytest.fixture
def secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "cron_secret", SecretStr(SECRET))
    monkeypatch.setattr(settings, "inbox_trigger_secret", SecretStr(INBOX_SECRET))


@pytest.fixture
def http() -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


def _freeze(monkeypatch: pytest.MonkeyPatch, now: datetime) -> None:
    monkeypatch.setattr(cron_service, "kyiv_now", lambda: now)


def _resident(hour: int, email: str) -> int:
    """A subscribed resident with one unsubmitted plot and the given reminder hour."""
    with Session(engine) as s:
        user = make_user(s, email=email)
        user.reminder_hour = hour
        make_household(s, name=f"Plot {email}", user_id=user.id)
        make_push_subscription(s, user_id=user.id)
        s.commit()
        return user.id


def _logs(variant: str | None = None) -> list[NotificationLog]:
    with Session(engine) as s:
        rows = list(s.exec(select(NotificationLog)).all())
    return [r for r in rows if variant is None or r.variant == variant]


class TestAuthentication:
    def test_route_is_hidden_and_does_nothing_when_secret_is_unset(
        self, http, monkeypatch, pushes, inbox
    ) -> None:
        monkeypatch.setattr(settings, "cron_secret", None)
        _freeze(monkeypatch, _kyiv(2027, 1, 1, 12))
        _resident(9, "a@example.com")

        res = http.post(URL, headers=_auth())

        assert res.status_code == 404
        assert _logs() == []
        pushes.assert_not_called()
        inbox.assert_not_called()

    def test_empty_secret_is_treated_as_unset(
        self, http, monkeypatch, pushes, inbox
    ) -> None:
        # An empty CRON_SECRET must not make an empty header a valid credential.
        monkeypatch.setattr(settings, "cron_secret", SecretStr(""))
        res = http.post(URL, headers={**CSRF, "X-Cron-Secret": ""})
        assert res.status_code == 404

    @pytest.mark.parametrize(
        "header",
        [
            pytest.param(None, id="missing"),
            pytest.param("wrong-secret-of-another-length", id="wrong"),
            pytest.param(SECRET[:-1], id="prefix-only"),
            pytest.param(SECRET + "x", id="secret-plus-suffix"),
            pytest.param("", id="empty"),
        ],
    )
    def test_rejects_anything_but_the_exact_secret(
        self, http, secret, monkeypatch, pushes, inbox, header
    ) -> None:
        _freeze(monkeypatch, _kyiv(2027, 1, 1, 12))
        _resident(9, "a@example.com")
        headers = dict(CSRF)
        if header is not None:
            headers["X-Cron-Secret"] = header

        res = http.post(URL, headers=headers)

        assert res.status_code == 401
        assert res.json() == {"detail": "invalidCronSecret"}
        assert _logs() == []
        inbox.assert_not_called()


class TestReminders:
    def test_sends_only_to_users_whose_reminder_hour_has_arrived(
        self, http, secret, monkeypatch, pushes, inbox
    ) -> None:
        # Jan 1 2027 (year rollover: period is 2026-12), 10:00 Kyiv.
        _freeze(monkeypatch, _kyiv(2027, 1, 1, 10))
        early = _resident(9, "early@example.com")
        exact = _resident(10, "exact@example.com")
        late = _resident(11, "late@example.com")

        body = http.post(URL, headers=_auth()).json()

        assert body["reminders_status"] == "ok"
        assert body["reminders_sent"] == 2
        assert {r.user_id for r in _logs("opening")} == {early, exact}
        assert late not in {r.user_id for r in _logs()}
        assert {r.period for r in _logs("opening")} == {"2026-12"}

    def test_later_tick_the_same_day_catches_up_users_not_yet_due(
        self, http, secret, monkeypatch, pushes, inbox
    ) -> None:
        early = _resident(9, "early@example.com")
        late = _resident(15, "late@example.com")

        _freeze(monkeypatch, _kyiv(2027, 1, 1, 10))
        assert http.post(URL, headers=_auth()).json()["reminders_sent"] == 1
        _freeze(monkeypatch, _kyiv(2027, 1, 1, 16))
        second = http.post(URL, headers=_auth()).json()

        assert second["reminders_sent"] == 1
        assert {r.user_id for r in _logs("opening")} == {early, late}

    def test_second_call_in_the_same_hour_sends_nothing(
        self, http, secret, monkeypatch, pushes, inbox
    ) -> None:
        _freeze(monkeypatch, _kyiv(2027, 1, 1, 12))
        _resident(9, "a@example.com")
        _resident(10, "b@example.com")

        first = http.post(URL, headers=_auth()).json()
        second = http.post(URL, headers=_auth()).json()

        assert first["reminders_sent"] == 2
        assert second["reminders_status"] == "ok"
        assert second["reminders_sent"] == 0
        assert pushes.call_count == 2

    def test_user_who_already_submitted_is_not_reminded(
        self, http, secret, monkeypatch, pushes, inbox
    ) -> None:
        _freeze(monkeypatch, _kyiv(2027, 1, 1, 12))
        done = _resident(9, "done@example.com")
        pending = _resident(9, "pending@example.com")
        with Session(engine) as s:
            hh = s.exec(select(Household).where(Household.user_id == done)).one()
            s.add(
                MeterReading(
                    household_id=hh.id,
                    period="2026-12",
                    day_meter_value=1,
                    night_meter_value=1,
                    source="resident",
                )
            )
            s.commit()

        http.post(URL, headers=_auth())

        assert {r.user_id for r in _logs("opening")} == {pending}

    def test_day_two_sends_no_reminder(
        self, http, secret, monkeypatch, pushes, inbox
    ) -> None:
        _freeze(monkeypatch, _kyiv(2027, 1, 2, 12))
        _resident(9, "a@example.com")

        body = http.post(URL, headers=_auth()).json()

        assert body["reminders_status"] == "ok"
        assert body["reminders_sent"] == 0
        assert _logs() == []

    def test_final_reminder_goes_out_on_day_five(
        self, http, secret, monkeypatch, pushes, inbox
    ) -> None:
        _freeze(monkeypatch, _kyiv(2027, 1, 5, 12))
        user = _resident(9, "a@example.com")

        http.post(URL, headers=_auth())

        assert [(r.user_id, r.variant) for r in _logs()] == [(user, "final")]


class TestMissingReadingsAdminNotice:
    def _admin(self) -> int:
        with Session(engine) as s:
            admin = make_user(s, email="admin@example.com", is_admin=True)
            make_push_subscription(s, user_id=admin.id)
            s.commit()
            return admin.id

    def test_admin_is_told_once_on_day_six_after_nine(
        self, http, secret, monkeypatch, pushes, inbox
    ) -> None:
        admin = self._admin()
        _resident(9, "silent@example.com")
        _freeze(monkeypatch, _kyiv(2027, 1, 6, 9))

        http.post(URL, headers=_auth())
        http.post(URL, headers=_auth())

        rows = _logs("missingReadings")
        assert [(r.user_id, r.period) for r in rows] == [(admin, "2026-12")]
        assert pushes.call_count == 1

    def test_admin_is_not_told_on_day_six_before_nine(
        self, http, secret, monkeypatch, pushes, inbox
    ) -> None:
        self._admin()
        _resident(9, "silent@example.com")
        _freeze(monkeypatch, _kyiv(2027, 1, 6, 8))

        res = http.post(URL, headers=_auth())

        assert res.json()["reminders_status"] == "ok"
        assert _logs() == []

    def test_admin_is_not_told_on_day_five(
        self, http, secret, monkeypatch, pushes, inbox
    ) -> None:
        # The window is still open on day 5; telling the admin who is "missing" is premature.
        admin = self._admin()
        _resident(23, "silent@example.com")
        _freeze(monkeypatch, _kyiv(2027, 1, 5, 12))

        http.post(URL, headers=_auth())

        assert admin not in {r.user_id for r in _logs("missingReadings")}


class TestInbox:
    def test_unconfigured_inbox_reports_so_and_reminders_still_run(
        self, http, secret, monkeypatch, pushes, inbox
    ) -> None:
        _freeze(monkeypatch, _kyiv(2027, 1, 1, 12))
        _resident(9, "a@example.com")

        res = http.post(URL, headers=_auth())

        assert res.status_code == 200
        body = res.json()
        assert body["inbox_status"] == "notConfigured"
        assert body["reminders_status"] == "ok"
        assert body["reminders_sent"] == 1

    def test_unreachable_mailbox_is_200_unavailable_not_a_failed_run(
        self, http, secret, monkeypatch, pushes, inbox
    ) -> None:
        inbox.side_effect = InboxUnavailableError()
        _freeze(monkeypatch, _kyiv(2027, 1, 1, 12))

        res = http.post(URL, headers=_auth())

        assert res.status_code == 200
        assert res.json()["inbox_status"] == "unavailable"
        assert res.json()["reminders_status"] == "ok"

    def test_inbox_counts_are_reported(
        self, http, secret, monkeypatch, pushes, inbox
    ) -> None:
        inbox.side_effect = None
        inbox.return_value = MagicMock(received=3, imported=2, rejected=1)
        _freeze(monkeypatch, _kyiv(2027, 1, 2, 12))

        body = http.post(URL, headers=_auth()).json()

        assert body["inbox_status"] == "ok"
        assert body["inbox"] == {"received": 3, "imported": 2, "rejected": 1}


class TestFailureIsolation:
    def test_reminder_failure_returns_500_but_inbox_check_still_runs(
        self, http, secret, monkeypatch, pushes, inbox
    ) -> None:
        boom = MagicMock(side_effect=RuntimeError("db exploded"))
        monkeypatch.setattr(cron_service, "send_reminders", boom)
        _freeze(monkeypatch, _kyiv(2027, 1, 1, 12))

        res = http.post(URL, headers=_auth())

        assert res.status_code == 500
        inbox.assert_called_once()

    def test_inbox_crash_does_not_stop_reminders_and_still_returns_200(
        self, http, secret, monkeypatch, pushes, inbox
    ) -> None:
        inbox.side_effect = RuntimeError("imap parser bug")
        _freeze(monkeypatch, _kyiv(2027, 1, 1, 12))
        _resident(9, "a@example.com")

        res = http.post(URL, headers=_auth())

        assert len(_logs("opening")) == 1
        # Product call: a crashed inbox is reported, not silently "ok".
        assert res.status_code == 200
        assert res.json()["inbox_status"] == "failed"


class TestConcurrentRuns:
    def _hold(self, key: int):
        conn = engine.connect()
        assert conn.execute(
            text("SELECT pg_try_advisory_lock(:k)"), {"k": key}
        ).scalar()
        return conn

    def _release(self, conn, key: int) -> None:
        conn.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": key})
        conn.commit()
        conn.close()

    def test_reminders_report_busy_and_send_nothing_while_another_run_holds_the_lock(
        self, http, secret, monkeypatch, pushes, inbox
    ) -> None:
        _freeze(monkeypatch, _kyiv(2027, 1, 1, 12))
        _resident(9, "a@example.com")
        conn = self._hold(cron_service._REMINDERS_LOCK)
        try:
            body = http.post(URL, headers=_auth()).json()
        finally:
            self._release(conn, cron_service._REMINDERS_LOCK)

        assert body["reminders_status"] == "busy"
        assert body["inbox_status"] == "notConfigured"
        assert _logs() == []

        # Once the other run finishes, the next tick does the work.
        assert http.post(URL, headers=_auth()).json()["reminders_sent"] == 1

    def test_inbox_reports_busy_while_another_run_holds_its_lock(
        self, http, secret, monkeypatch, pushes, inbox
    ) -> None:
        _freeze(monkeypatch, _kyiv(2027, 1, 2, 12))
        conn = self._hold(cron_service._INBOX_LOCK)
        try:
            body = http.post(URL, headers=_auth()).json()
        finally:
            self._release(conn, cron_service._INBOX_LOCK)

        assert body["inbox_status"] == "busy"
        assert body["reminders_status"] == "ok"
        inbox.assert_not_called()


class TestInboxOnly:
    """`POST /internal/inbox/check` (issue #358): the bank-inbox check alone."""

    INBOX_URL = "/internal/inbox/check"

    def test_route_is_hidden_when_secret_is_unset(
        self, http, monkeypatch, inbox
    ) -> None:
        monkeypatch.setattr(settings, "inbox_trigger_secret", None)

        res = http.post(self.INBOX_URL, headers=_auth(INBOX_SECRET))

        assert res.status_code == 404
        inbox.assert_not_called()

    def test_the_tick_secret_does_not_open_the_inbox_route(
        self, http, secret, inbox
    ) -> None:
        res = http.post(self.INBOX_URL, headers=_auth(SECRET))

        assert res.status_code == 401
        inbox.assert_not_called()

    @pytest.mark.parametrize(
        "header",
        [
            pytest.param(None, id="missing"),
            pytest.param("wrong-secret-of-another-length", id="wrong"),
            pytest.param(INBOX_SECRET + "x", id="secret-plus-suffix"),
        ],
    )
    def test_rejects_anything_but_the_exact_secret_and_runs_nothing(
        self, http, secret, inbox, header
    ) -> None:
        headers = dict(CSRF)
        if header is not None:
            headers["X-Cron-Secret"] = header

        res = http.post(self.INBOX_URL, headers=headers)

        assert res.status_code == 401
        assert res.json() == {"detail": "invalidCronSecret"}
        inbox.assert_not_called()

    def test_reports_inbox_counts_when_the_check_succeeds(
        self, http, secret, inbox
    ) -> None:
        inbox.side_effect = None
        inbox.return_value = MagicMock(received=7, imported=4, rejected=3)

        res = http.post(self.INBOX_URL, headers=_auth(INBOX_SECRET))

        assert res.status_code == 200
        body = res.json()
        assert body["inbox_status"] == "ok"
        assert body["inbox"] == {"received": 7, "imported": 4, "rejected": 3}

    def test_unconfigured_inbox_is_reported_as_not_configured(
        self, http, secret, inbox
    ) -> None:
        res = http.post(self.INBOX_URL, headers=_auth(INBOX_SECRET))

        assert res.status_code == 200
        assert res.json()["inbox_status"] == "notConfigured"

    def test_unreachable_mailbox_is_200_unavailable(self, http, secret, inbox) -> None:
        inbox.side_effect = InboxUnavailableError()

        res = http.post(self.INBOX_URL, headers=_auth(INBOX_SECRET))

        assert res.status_code == 200
        assert res.json()["inbox_status"] == "unavailable"

    def test_reports_busy_and_skips_the_check_while_another_run_holds_the_lock(
        self, http, secret, inbox
    ) -> None:
        conn = TestConcurrentRuns()._hold(cron_service._INBOX_LOCK)
        try:
            res = http.post(self.INBOX_URL, headers=_auth(INBOX_SECRET))
        finally:
            TestConcurrentRuns()._release(conn, cron_service._INBOX_LOCK)

        assert res.status_code == 200
        assert res.json()["inbox_status"] == "busy"
        inbox.assert_not_called()

    def test_does_not_send_reminders_even_when_one_is_due(
        self, http, secret, monkeypatch, pushes, inbox
    ) -> None:
        # Jan 1, 12:00 Kyiv: a tick would remind this resident.
        _freeze(monkeypatch, _kyiv(2027, 1, 1, 12))
        _resident(9, "a@example.com")

        res = http.post(self.INBOX_URL, headers=_auth(INBOX_SECRET))

        assert res.status_code == 200
        pushes.assert_not_called()
        assert _logs() == []

    def test_unexpected_inbox_crash_returns_500_so_the_caller_sees_it(
        self, http, secret, inbox
    ) -> None:
        inbox.side_effect = RuntimeError("imap parser bug")

        res = http.post(self.INBOX_URL, headers=_auth(INBOX_SECRET))

        assert res.status_code == 500


class TestSecretHygiene:
    def test_secret_never_appears_in_logs_on_success_failure_or_rejection(
        self, http, secret, monkeypatch, pushes, inbox, caplog
    ) -> None:
        caplog.set_level(logging.DEBUG)
        _freeze(monkeypatch, _kyiv(2027, 1, 1, 12))
        http.post(URL, headers=_auth())
        http.post(URL, headers=_auth(SECRET[:-1]))
        monkeypatch.setattr(
            cron_service, "send_reminders", MagicMock(side_effect=RuntimeError("x"))
        )
        http.post(URL, headers=_auth())

        assert SECRET not in caplog.text
        assert SECRET not in repr(settings.cron_secret)
