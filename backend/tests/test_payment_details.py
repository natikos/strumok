"""Co-op payment details (IBAN) shown to residents and edited by the head."""

from sqlmodel import Session, select

from app.api.billing.payment_details import InvalidIbanError, normalize_iban
from app.db.models import AuditLog
from tests.factories import authenticate, make_household, make_user

# Valid UA IBAN (passes mod-97) and a copy with one digit changed.
IBAN = "UA213223130000026007233566001"
BAD_IBAN = "UA213223130000026007233566002"


def _put(client, **overrides):
    body = {"iban": IBAN, "recipient_name": "Strumok Co-op", **overrides}
    return client.put("/admin/payment-details", json=body)


class TestNormalizeIban:
    def test_strips_spaces_and_uppercases(self) -> None:
        spaced = "ua21 3223 1300 0002 6007 2335 6600 1"
        assert normalize_iban(spaced) == IBAN

    def test_rejects_bad_checksum(self) -> None:
        try:
            normalize_iban(BAD_IBAN)
        except InvalidIbanError:
            return
        raise AssertionError("expected InvalidIbanError")

    def test_rejects_wrong_length_and_country(self) -> None:
        for raw in (IBAN[:-1], "DE" + IBAN[2:], ""):
            try:
                normalize_iban(raw)
            except InvalidIbanError:
                continue
            raise AssertionError(f"accepted {raw!r}")


class TestAdminWrite:
    def test_admin_sets_and_reads_details(self, client, session: Session) -> None:
        authenticate(client, make_user(session, is_admin=True))
        assert client.get("/admin/payment-details").json() is None
        res = _put(client, iban=" ua21 3223 1300 0002 6007 2335 6600 1 ")
        assert res.status_code == 200
        assert res.json() == {"iban": IBAN, "recipient_name": "Strumok Co-op"}
        assert client.get("/admin/payment-details").json()["iban"] == IBAN

    def test_change_is_audited_with_before_and_after(
        self, client, session: Session
    ) -> None:
        authenticate(client, make_user(session, is_admin=True))
        _put(client)
        _put(client, recipient_name="New Name")
        entries = session.exec(
            select(AuditLog)
            .where(AuditLog.action == "payment_details.set")
            .order_by(AuditLog.id)
        ).all()
        assert len(entries) == 2
        assert entries[0].before is None
        assert entries[1].before["recipient_name"] == "Strumok Co-op"
        assert entries[1].after["recipient_name"] == "New Name"

    def test_invalid_iban_rejected_with_stable_code(
        self, client, session: Session
    ) -> None:
        authenticate(client, make_user(session, is_admin=True))
        res = _put(client, iban=BAD_IBAN)
        assert res.status_code == 422
        assert res.json()["detail"] == "invalidIban"

    def test_resident_cannot_write(self, client, session: Session) -> None:
        authenticate(client, make_user(session))
        assert _put(client).status_code == 403


class TestResidentRead:
    def test_returns_null_until_configured(self, client, session: Session) -> None:
        resident = make_user(session)
        make_household(session, user_id=resident.id)
        authenticate(client, resident)
        res = client.get("/billing/payment-details")
        assert res.status_code == 200
        assert res.json() is None

    def test_returns_details_to_resident_with_household(
        self, client, session: Session
    ) -> None:
        authenticate(client, make_user(session, is_admin=True))
        _put(client)
        resident = make_user(session)
        make_household(session, user_id=resident.id)
        authenticate(client, resident)
        res = client.get("/billing/payment-details")
        assert res.json() == {"iban": IBAN, "recipient_name": "Strumok Co-op"}

    def test_requires_a_household(self, client, session: Session) -> None:
        authenticate(client, make_user(session))
        res = client.get("/billing/payment-details")
        assert res.status_code == 404
        assert res.json()["detail"] == "noHouseholdMembership"

    def test_requires_authentication(self, client) -> None:
        assert client.get("/billing/payment-details").status_code == 401
