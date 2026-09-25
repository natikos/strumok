"""Coverage for Web Push (VAPID) reminder notifications (issue #94).

`send_reminders` is the part worth the most scrutiny: it decides, for every
subscribed user, whether *every* household they own already has a reading for
the current billing period, and only then skips them. A resident with two
households who submitted one and forgot the other must still get reminded.
`pywebpush.webpush` is mocked throughout -- these tests never touch the
network -- and the 404/410-vs-everything-else branch is exercised precisely
because it's the difference between "this subscription is dead, forget it"
and "this failure was transient, keep it".
"""

from unittest.mock import MagicMock, patch

import pytest
from app.api.push.service import (
    delete_subscription,
    send_reminders,
    upsert_subscription,
)
from app.core.domain import current_billing_period
from app.core.config import settings
from app.db.models import PushSubscription
from pydantic import SecretStr
from pywebpush import WebPushException
from sqlmodel import Session, select
from tests.factories import (
    authenticate,
    make_household,
    make_meter_reading,
    make_push_subscription,
    make_user,
)


def _fake_webpush_exception(status_code: int) -> WebPushException:
    response = MagicMock()
    response.status_code = status_code
    return WebPushException("push failed", response=response)


class TestUpsertSubscription:
    def test_creates_a_new_subscription_for_a_first_time_endpoint(
        self, session: Session
    ) -> None:
        user = make_user(session)

        subscription = upsert_subscription(
            session=session,
            user=user,
            endpoint="https://push.example.com/new-device",
            p256dh="p256dh-1",
            auth="auth-1",
        )

        assert subscription.id is not None
        assert subscription.user_id == user.id
        stored = session.exec(
            select(PushSubscription).where(
                PushSubscription.endpoint == "https://push.example.com/new-device"
            )
        ).one()
        assert stored.p256dh == "p256dh-1"
        assert stored.auth == "auth-1"

    def test_reassigns_an_existing_endpoint_to_a_new_owner_and_refreshes_its_keys(
        self, session: Session
    ) -> None:
        # A browser can resubscribe the same push endpoint under a different
        # logged-in user (e.g. a shared device); the row must follow the new
        # owner and pick up the fresh keys rather than erroring as a duplicate
        # or silently keeping the stale owner/keys.
        original_owner = make_user(session, email="first-owner@example.com")
        new_owner = make_user(session, email="second-owner@example.com")
        existing = make_push_subscription(
            session,
            user_id=original_owner.id,
            endpoint="https://push.example.com/shared-device",
            p256dh="stale-key",
            auth="stale-auth",
        )

        result = upsert_subscription(
            session=session,
            user=new_owner,
            endpoint="https://push.example.com/shared-device",
            p256dh="fresh-key",
            auth="fresh-auth",
        )

        assert result.id == existing.id
        assert result.user_id == new_owner.id
        assert result.p256dh == "fresh-key"
        assert result.auth == "fresh-auth"
        rows = session.exec(
            select(PushSubscription).where(
                PushSubscription.endpoint == "https://push.example.com/shared-device"
            )
        ).all()
        assert len(rows) == 1


class TestDeleteSubscription:
    def test_deletes_a_subscription_owned_by_the_caller(self, session: Session) -> None:
        user = make_user(session)
        make_push_subscription(
            session, user_id=user.id, endpoint="https://push.example.com/mine"
        )

        delete_subscription(
            session=session, user=user, endpoint="https://push.example.com/mine"
        )

        assert (
            session.exec(
                select(PushSubscription).where(
                    PushSubscription.endpoint == "https://push.example.com/mine"
                )
            ).first()
            is None
        )

    def test_is_a_silent_no_op_for_an_endpoint_that_was_never_subscribed(
        self, session: Session
    ) -> None:
        user = make_user(session)

        # Must not raise.
        delete_subscription(
            session=session,
            user=user,
            endpoint="https://push.example.com/never-existed",
        )

    def test_does_not_delete_a_subscription_owned_by_a_different_user(
        self, session: Session
    ) -> None:
        owner = make_user(session, email="owner@example.com")
        intruder = make_user(session, email="intruder@example.com")
        make_push_subscription(
            session, user_id=owner.id, endpoint="https://push.example.com/not-yours"
        )

        delete_subscription(
            session=session,
            user=intruder,
            endpoint="https://push.example.com/not-yours",
        )

        assert (
            session.exec(
                select(PushSubscription).where(
                    PushSubscription.endpoint == "https://push.example.com/not-yours"
                )
            ).first()
            is not None
        )


class TestSendReminders:
    def test_skips_a_user_whose_every_household_already_submitted(
        self, session: Session
    ) -> None:
        period = current_billing_period()
        user = make_user(session)
        household = make_household(session, user_id=user.id)
        make_meter_reading(session, household_id=household.id, period=period)
        make_push_subscription(session, user_id=user.id)

        with patch("app.api.push.service.webpush") as mock_webpush:
            sent, removed = send_reminders(session=session, variant="opening")

        assert (sent, removed) == (0, 0)
        mock_webpush.assert_not_called()

    def test_sends_when_only_one_of_two_households_has_submitted(
        self, session: Session
    ) -> None:
        # The resident submitted for one plot and forgot the other -- they
        # must still be reminded, not skipped because *a* household is done.
        period = current_billing_period()
        user = make_user(session)
        submitted = make_household(session, user_id=user.id, name="Submitted plot")
        make_household(session, user_id=user.id, name="Forgotten plot")
        make_meter_reading(session, household_id=submitted.id, period=period)
        make_push_subscription(session, user_id=user.id)

        with patch("app.api.push.service.webpush") as mock_webpush:
            sent, removed = send_reminders(session=session, variant="opening")

        assert (sent, removed) == (1, 0)
        mock_webpush.assert_called_once()

    def test_sends_to_every_device_the_user_has_subscribed(
        self, session: Session
    ) -> None:
        user = make_user(session)
        make_household(session, user_id=user.id)
        make_push_subscription(
            session, user_id=user.id, endpoint="https://push.example.com/phone"
        )
        make_push_subscription(
            session, user_id=user.id, endpoint="https://push.example.com/tablet"
        )

        with patch("app.api.push.service.webpush") as mock_webpush:
            sent, removed = send_reminders(session=session, variant="final")

        assert (sent, removed) == (2, 0)
        assert mock_webpush.call_count == 2

    def test_skips_a_subscribed_user_who_owns_no_household(
        self, session: Session
    ) -> None:
        user = make_user(session)
        make_push_subscription(session, user_id=user.id)

        with patch("app.api.push.service.webpush") as mock_webpush:
            sent, removed = send_reminders(session=session, variant="opening")

        assert (sent, removed) == (0, 0)
        mock_webpush.assert_not_called()

    def test_an_unowned_household_does_not_count_toward_anyones_submission_status(
        self, session: Session
    ) -> None:
        period = current_billing_period()
        user = make_user(session)
        make_household(session, user_id=None, name="Unowned plot")
        household = make_household(session, user_id=user.id)
        make_meter_reading(session, household_id=household.id, period=period)
        make_push_subscription(session, user_id=user.id)

        with patch("app.api.push.service.webpush") as mock_webpush:
            sent, removed = send_reminders(session=session, variant="opening")

        # The user's only owned household already submitted, so they must be
        # skipped -- the unowned household must not be attributed to them.
        assert (sent, removed) == (0, 0)
        mock_webpush.assert_not_called()

    @pytest.mark.parametrize("status_code", [404, 410])
    def test_removes_a_subscription_the_push_service_reports_as_gone(
        self, session: Session, status_code: int
    ) -> None:
        user = make_user(session)
        make_household(session, user_id=user.id)
        subscription = make_push_subscription(session, user_id=user.id)

        with patch(
            "app.api.push.service.webpush",
            side_effect=_fake_webpush_exception(status_code),
        ):
            sent, removed = send_reminders(session=session, variant="opening")

        assert (sent, removed) == (0, 1)
        assert (
            session.exec(
                select(PushSubscription).where(PushSubscription.id == subscription.id)
            ).first()
            is None
        )

    def test_a_non_gone_push_failure_is_swallowed_and_the_subscription_survives(
        self, session: Session
    ) -> None:
        # A 500 is a transient failure of the push service, not evidence the
        # subscription is dead -- unlike 404/410, it must not be deleted, and
        # it must not be miscounted as a successful send either.
        user = make_user(session)
        make_household(session, user_id=user.id)
        subscription = make_push_subscription(session, user_id=user.id)

        with patch(
            "app.api.push.service.webpush", side_effect=_fake_webpush_exception(500)
        ):
            sent, removed = send_reminders(session=session, variant="opening")

        assert (sent, removed) == (0, 0)
        assert (
            session.exec(
                select(PushSubscription).where(PushSubscription.id == subscription.id)
            ).first()
            is not None
        )

    def test_one_users_failed_send_does_not_stop_another_users_reminder(
        self, session: Session
    ) -> None:
        failing_user = make_user(session, email="failing@example.com")
        make_household(session, user_id=failing_user.id)
        make_push_subscription(
            session,
            user_id=failing_user.id,
            endpoint="https://push.example.com/failing",
        )

        healthy_user = make_user(session, email="healthy@example.com")
        make_household(session, user_id=healthy_user.id)
        make_push_subscription(
            session,
            user_id=healthy_user.id,
            endpoint="https://push.example.com/healthy",
        )

        def side_effect(*, subscription_info: dict, **_kwargs: object) -> None:
            if subscription_info["endpoint"] == "https://push.example.com/failing":
                raise _fake_webpush_exception(410)

        with patch("app.api.push.service.webpush", side_effect=side_effect):
            sent, removed = send_reminders(session=session, variant="opening")

        assert (sent, removed) == (1, 1)


class TestGetVapidPublicKeyRoute:
    def test_returns_the_configured_public_key_without_requiring_auth(
        self, client, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings.push, "vapid_public_key", "test-vapid-public-key")

        response = client.get("/push/vapid-public-key")

        assert response.status_code == 200
        assert response.json() == {"public_key": "test-vapid-public-key"}


class TestSubscribeRoute:
    def test_requires_authentication(self, client) -> None:
        response = client.post(
            "/push/subscribe",
            json={
                "endpoint": "https://push.example.com/x",
                "keys": {"p256dh": "a", "auth": "b"},
            },
        )

        assert response.status_code == 401

    def test_stores_a_subscription_for_the_authenticated_user(
        self, client, session: Session
    ) -> None:
        user = make_user(session, email="subscriber@example.com")
        authenticate(client, user)

        response = client.post(
            "/push/subscribe",
            json={
                "endpoint": "https://push.example.com/new-device",
                "keys": {"p256dh": "p", "auth": "a"},
            },
        )

        assert response.status_code == 204
        stored = session.exec(
            select(PushSubscription).where(
                PushSubscription.endpoint == "https://push.example.com/new-device"
            )
        ).one()
        assert stored.user_id == user.id

    def test_rejects_a_malformed_body(self, client, session: Session) -> None:
        user = make_user(session)
        authenticate(client, user)

        response = client.post(
            "/push/subscribe", json={"endpoint": "https://push.example.com/bad"}
        )

        assert response.status_code == 422


class TestUnsubscribeRoute:
    def test_requires_authentication(self, client) -> None:
        response = client.request(
            "DELETE", "/push/subscribe", json={"endpoint": "https://push.example.com/x"}
        )

        assert response.status_code == 401

    def test_returns_204_for_an_endpoint_that_was_never_subscribed(
        self, client, session: Session
    ) -> None:
        user = make_user(session)
        authenticate(client, user)

        response = client.request(
            "DELETE",
            "/push/subscribe",
            json={"endpoint": "https://push.example.com/never-subscribed"},
        )

        assert response.status_code == 204

    def test_removes_an_existing_subscription_and_returns_204(
        self, client, session: Session
    ) -> None:
        user = make_user(session)
        authenticate(client, user)
        make_push_subscription(
            session, user_id=user.id, endpoint="https://push.example.com/to-remove"
        )

        response = client.request(
            "DELETE",
            "/push/subscribe",
            json={"endpoint": "https://push.example.com/to-remove"},
        )

        assert response.status_code == 204
        assert (
            session.exec(
                select(PushSubscription).where(
                    PushSubscription.endpoint == "https://push.example.com/to-remove"
                )
            ).first()
            is None
        )


class TestSendRemindersInternalRoute:
    def test_rejects_a_missing_secret(self, client) -> None:
        response = client.post(
            "/internal/push/send-reminders", params={"variant": "opening"}
        )

        assert response.status_code == 401
        assert response.json()["detail"] == "invalidInternalSecret"

    def test_rejects_a_wrong_secret(
        self, client, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            settings.auth, "internal_secret", SecretStr("correct-secret")
        )

        response = client.post(
            "/internal/push/send-reminders",
            params={"variant": "opening"},
            headers={"X-Internal-Secret": "wrong-secret"},
        )

        assert response.status_code == 401
        assert response.json()["detail"] == "invalidInternalSecret"

    def test_accepts_the_correct_secret_and_reports_send_counts(
        self, client, session: Session, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            settings.auth, "internal_secret", SecretStr("correct-secret")
        )
        user = make_user(session)
        make_household(session, user_id=user.id)
        make_push_subscription(session, user_id=user.id)

        with patch("app.api.push.service.webpush"):
            response = client.post(
                "/internal/push/send-reminders",
                params={"variant": "opening"},
                headers={"X-Internal-Secret": "correct-secret"},
            )

        assert response.status_code == 200
        assert response.json() == {"sent": 1, "removed": 0}

    def test_is_not_exposed_in_the_public_openapi_schema(self, client) -> None:
        # Reachable but deliberately undocumented -- it's an internal endpoint
        # for a scheduler, not part of the public API surface.
        schema = client.app.openapi()

        assert "/internal/push/send-reminders" not in schema["paths"]
