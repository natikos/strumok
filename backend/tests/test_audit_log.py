"""The audit log is append-only and commits atomically with the audited change."""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlmodel import Session, select

from app.core import audit
from app.db.models import APPEND_ONLY_TABLES, AuditLog
from tests.factories import authenticate, make_household, make_user


def _entries(session: Session, action: str) -> list[AuditLog]:
    return list(session.exec(select(AuditLog).where(AuditLog.action == action)))


class TestAppendOnly:
    @pytest.mark.parametrize(
        "statement", ["UPDATE audit_log SET action = 'x'", "DELETE FROM audit_log"]
    )
    def test_update_and_delete_fail_in_the_database(
        self, session: Session, statement: str
    ) -> None:
        audit.record(session, actor_user_id=None, action="probe", entity_type="x")
        session.flush()

        with pytest.raises(DBAPIError, match="append-only"):
            session.execute(text(statement))

    @pytest.mark.parametrize("table", APPEND_ONLY_TABLES)
    def test_truncate_fails_in_the_database(self, session: Session, table: str) -> None:
        """Row-level triggers don't fire for TRUNCATE; a statement trigger does."""
        with pytest.raises(DBAPIError, match="append-only"):
            session.execute(text(f"TRUNCATE {table}"))


class TestAtomicity:
    def test_audit_row_rolls_back_with_the_change(self, session: Session) -> None:
        audit.record(session, actor_user_id=None, action="rolledBack", entity_type="x")
        session.flush()

        session.rollback()

        assert _entries(session, "rolledBack") == []


class TestWiredActions:
    def test_household_creation_and_owner_assignment_are_audited(
        self, client, session: Session
    ) -> None:
        admin = make_user(session, is_admin=True)
        owner = make_user(session)
        other = make_user(session)
        authenticate(client, admin)

        created = client.post(
            "/admin/households", json={"name": "Plot 7", "user_id": owner.id}
        ).json()
        client.patch(
            f"/admin/households/{created['id']}/owner",
            json={
                "user_id": other.id,
                "confirm_reassignment": True,
                "handover_day_meter_value": "10",
                "handover_night_meter_value": "5",
            },
        )

        (made,) = _entries(session, "householdCreated")
        assert made.actor_user_id == admin.id
        assert made.household_id == created["id"]
        assert made.after == {"name": "Plot 7", "user_id": owner.id}
        (moved,) = _entries(session, "householdTransferred")
        assert moved.before == {"user_id": owner.id}
        assert moved.after == {
            "user_id": other.id,
            "handover_day": "10",
            "handover_night": "5",
            "balance_acknowledged": False,
        }

    def test_rate_creation_is_audited_with_decimals_as_strings(
        self, client, session: Session
    ) -> None:
        admin = make_user(session, is_admin=True)
        authenticate(client, admin)

        response = client.post(
            "/electricity-rates",
            json={
                "day_rate_uah": "4.32",
                "night_rate_uah": "2.16",
                "effective_from": "2030-01",
            },
        )

        assert response.status_code == 201
        (entry,) = _entries(session, "rateCreated")
        assert entry.period == "2030-01"
        assert entry.after["day_rate_uah"] == "4.32"


class TestAuditLogEndpoint:
    def test_requires_admin(self, client, session: Session) -> None:
        authenticate(client, make_user(session))
        assert client.get("/admin/audit-log").status_code == 403

    def test_filters_by_household_and_paginates_newest_first(
        self, client, session: Session
    ) -> None:
        admin = make_user(session, is_admin=True)
        household = make_household(session, user_id=make_user(session).id)
        other = make_household(session, user_id=make_user(session).id)
        for i in range(3):
            audit.record(
                session,
                actor_user_id=admin.id,
                action="probe",
                entity_type="household",
                household_id=household.id,
                period=f"2030-0{i + 1}",
            )
        audit.record(
            session,
            actor_user_id=None,
            action="probe",
            entity_type="household",
            household_id=other.id,
        )
        session.flush()
        authenticate(client, admin)

        body = client.get(f"/admin/audit-log?household_id={household.id}").json()
        assert [e["period"] for e in body["items"]] == ["2030-03", "2030-02", "2030-01"]
        assert body["items"][0]["actor"]["id"] == admin.id
        assert body["next_cursor"] is None

        by_period = client.get(
            f"/admin/audit-log?household_id={household.id}&period=2030-02"
        ).json()
        assert len(by_period["items"]) == 1
