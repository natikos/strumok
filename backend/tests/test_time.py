"""Every datetime the API returns must carry a UTC offset.

A naive ISO string ("2026-07-20T08:40:50") is parsed as *local* time by browsers,
so a Kyiv resident's `submitted_at` shifts by 2-3 hours and can flip an on-time
submission to "late" (issue #142).
"""

from datetime import datetime, timedelta, timezone
from typing import get_args, get_origin

import pytest
from fastapi.routing import APIRoute
from pydantic import BaseModel, TypeAdapter
from sqlmodel import Session

from app.core.time import to_utc_iso
from app.main import app
from tests.factories import (
    authenticate,
    make_electricity_rate,
    make_household,
    make_user,
)

NAIVE_UTC = datetime(2026, 7, 5, 20, 30, 0)


def _contains_datetime(annotation: object) -> bool:
    if annotation is datetime:
        return True
    return any(_contains_datetime(arg) for arg in get_args(annotation))


def _nested_models(annotation: object) -> list[type[BaseModel]]:
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return [annotation]
    if get_origin(annotation) is not None:
        return [m for arg in get_args(annotation) for m in _nested_models(arg)]
    return []


def _response_models() -> set[type[BaseModel]]:
    seen: set[type[BaseModel]] = set()
    pending = [
        model
        for route in app.routes
        if isinstance(route, APIRoute) and route.response_model is not None
        for model in _nested_models(route.response_model)
    ]
    while pending:
        model = pending.pop()
        if model in seen:
            continue
        seen.add(model)
        for field in model.model_fields.values():
            pending.extend(_nested_models(field.annotation))
    return seen


def _datetime_fields() -> list[tuple[type[BaseModel], str]]:
    return [
        (model, name)
        for model in _response_models()
        for name, field in model.model_fields.items()
        if _contains_datetime(field.annotation)
    ]


def test_sweep_finds_the_known_datetime_fields() -> None:
    # Guards the sweep itself: if it silently found nothing, the parametrized
    # test below would pass vacuously.
    names = {f"{model.__name__}.{name}" for model, name in _datetime_fields()}
    assert "MeterReadingOut.submitted_at" in names
    assert "AdminDashboardHouseholdOut.submitted_at" in names


@pytest.mark.parametrize(
    ("model", "field_name"),
    _datetime_fields(),
    ids=lambda v: v.__name__ if isinstance(v, type) else v,
)
def test_every_response_datetime_serializes_as_utc_with_z(
    model: type[BaseModel], field_name: str
) -> None:
    adapter = TypeAdapter(model.model_fields[field_name].annotation)

    assert adapter.dump_python(NAIVE_UTC, mode="json") == "2026-07-05T20:30:00Z"


class TestToUtcIso:
    def test_naive_value_is_treated_as_utc(self) -> None:
        assert to_utc_iso(NAIVE_UTC) == "2026-07-05T20:30:00Z"

    def test_aware_value_is_converted_to_utc(self) -> None:
        kyiv_summer = timezone(timedelta(hours=3))
        aware = datetime(2026, 7, 5, 23, 30, tzinfo=kyiv_summer)

        assert to_utc_iso(aware) == "2026-07-05T20:30:00Z"

    def test_microseconds_are_kept(self) -> None:
        assert (
            to_utc_iso(datetime(2026, 7, 20, 8, 40, 50, 453000))
            == "2026-07-20T08:40:50.453000Z"
        )


def test_submitted_at_in_meter_reading_response_ends_in_z(
    client, session: Session
) -> None:
    user = make_user(session, email="tz@example.com")
    household = make_household(session, user_id=user.id)
    make_electricity_rate(session, effective_from="2000-01")
    authenticate(client, user)

    response = client.post(
        "/meter-readings",
        params={"household_id": household.id},
        json={
            "period": "2026-07",
            "day_meter_value": "100.00",
            "night_meter_value": "50.00",
        },
    )

    assert response.status_code == 201, response.text
    assert response.json()["submitted_at"].endswith("Z")
