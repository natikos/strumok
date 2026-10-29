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


# Strict: once #271 is fixed this passes, the xfail turns red, and the mark
# must come off.
@pytest.mark.xfail(
    strict=True,
    reason="#271: tenure filtering hides the open period from a new owner",
)
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
            json={"user_id": resident.id, "confirm_reassignment": True},
        ).status_code
        == 200
    )

    authenticate(client, resident)
    submitted = client.post(
        f"/meter-readings?household_id={household_id}",
        json={"period": "2026-06", "day_meter_value": 1234, "night_meter_value": 567},
    )
    assert submitted.status_code == 201

    listed = client.get(f"/meter-readings?household_id={household_id}").json()
    assert "2026-06" in [row["period"] for row in listed]
