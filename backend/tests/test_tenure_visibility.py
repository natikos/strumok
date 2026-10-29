"""A resident's own submission must stay visible to them."""

from datetime import datetime, timedelta, timezone

import pytest
from sqlmodel import Session
from starlette.testclient import TestClient

from app.core.time import set_clock_offset
from tests.factories import authenticate, make_electricity_rate, make_user


@pytest.fixture(autouse=True)
def _restore_clock():
    yield
    set_clock_offset(timedelta(0))


def test_reading_for_the_open_period_is_listed_for_an_owner_assigned_this_month(
    client: TestClient, session: Session
) -> None:
    # Kyiv day 2 of July: residents submit June's reading.
    target = datetime(2026, 7, 2, 12, 0, tzinfo=timezone(timedelta(hours=3)))
    set_clock_offset(target - datetime.now(timezone.utc))
    make_electricity_rate(session, effective_from="2026-06")
    admin = make_user(session, is_admin=True)
    resident = make_user(session)

    authenticate(client, admin)
    created = client.post(
        "/admin/households", json={"name": "Plot 7", "user_id": admin.id}
    )
    household_id = created.json()["id"]
    assert (
        client.patch(
            f"/admin/households/{household_id}/owner",
            json={"user_id": None, "confirm_reassignment": True},
        ).status_code
        == 200
    )
    assert (
        client.patch(
            f"/admin/households/{household_id}/owner",
            json={
                "user_id": resident.id,
                "confirm_reassignment": True,
                "handover_day_meter_value": "1234",
                "handover_night_meter_value": "567",
            },
        ).status_code
        == 200
    )

    authenticate(client, resident)

    listed = client.get(f"/meter-readings?household_id={household_id}").json()
    assert "2026-06" in [row["period"] for row in listed]


def _transfer_on_day(client: TestClient, session: Session, day: int):
    target = datetime(2026, 7, day, 12, 0, tzinfo=timezone(timedelta(hours=3)))
    set_clock_offset(target - datetime.now(timezone.utc))
    make_electricity_rate(session, effective_from="2026-06")
    admin = make_user(session, is_admin=True)
    old_owner = make_user(session)
    new_owner = make_user(session)

    authenticate(client, admin)
    household_id = client.post(
        "/admin/households", json={"name": "Plot 8", "user_id": old_owner.id}
    ).json()["id"]
    transferred = client.patch(
        f"/admin/households/{household_id}/owner",
        json={
            "user_id": new_owner.id,
            "confirm_reassignment": True,
            "handover_day_meter_value": "150",
            "handover_night_meter_value": "40",
        },
    )
    assert transferred.status_code == 200
    return household_id, new_owner


def test_handover_during_the_window_stands_in_for_the_open_period(
    client: TestClient, session: Session
) -> None:
    household_id, new_owner = _transfer_on_day(client, session, 2)

    authenticate(client, new_owner)
    listed = client.get(f"/meter-readings?household_id={household_id}").json()
    june = next(row for row in listed if row["period"] == "2026-06")
    assert june["id"] is not None
    assert june["source"] == "admin"
    assert june["day_meter_value"] == "150.00"

    retry = client.post(
        f"/meter-readings?household_id={household_id}",
        json={"period": "2026-06", "day_meter_value": 160, "night_meter_value": 45},
    )
    assert retry.status_code == 409


def test_handover_after_the_window_leaves_the_open_period_to_the_old_owner(
    client: TestClient, session: Session
) -> None:
    household_id, new_owner = _transfer_on_day(client, session, 10)

    authenticate(client, new_owner)
    listed = client.get(f"/meter-readings?household_id={household_id}").json()
    assert "2026-06" not in [row["period"] for row in listed]


def test_new_owner_gets_no_provisional_line_for_the_outgoing_owners_period(
    client: TestClient, session: Session
) -> None:
    household_id, new_owner = _transfer_on_day(client, session, 2)

    authenticate(client, new_owner)
    statements = client.get(f"/billing/statements?household_id={household_id}")
    assert "2026-06" not in [row["period"] for row in statements.json()]
