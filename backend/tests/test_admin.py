"""Coverage for the admin household-assignment endpoints.

These routes let an admin fix data a resident can't touch themselves: create a
household for a user, or (re)assign/unassign a household's owner. The costly
mistakes here are an unconfirmed reassignment silently overwriting an existing
owner (including silently unassigning one), and privilege escalation through a
missing or bypassed `require_admin` check.
"""

from decimal import Decimal

from app.api.admin.service import _summed_usage_kwh
from sqlmodel import Session
from tests.factories import authenticate, make_household, make_meter_reading, make_user

ADMIN_ROUTES_REQUIRING_AUTH = [
    ("get", "/admin/users"),
    ("get", "/admin/households"),
    ("get", "/admin/dashboard"),
]


class TestRequireAdmin:
    def test_no_cookie_is_unauthorized(self, client) -> None:
        for method, path in ADMIN_ROUTES_REQUIRING_AUTH:
            response = getattr(client, method)(path)
            assert response.status_code == 401, (path, response.text)

    def test_post_households_without_cookie_is_unauthorized(self, client) -> None:
        response = client.post(
            "/admin/households", json={"name": "Plot 1", "user_id": 1}
        )
        assert response.status_code == 401

    def test_patch_owner_without_cookie_is_unauthorized(self, client) -> None:
        response = client.patch("/admin/households/1/owner", json={"user_id": 1})
        assert response.status_code == 401

    def test_non_admin_user_is_forbidden(self, client, session: Session) -> None:
        user = make_user(session, email="regular@example.com", is_admin=False)
        authenticate(client, user)

        response = client.get("/admin/users")

        assert response.status_code == 403
        assert response.json()["detail"] == "adminPrivilegesRequired"

    def test_admin_user_is_allowed_through(self, client, session: Session) -> None:
        admin = make_user(session, email="admin@example.com", is_admin=True)
        authenticate(client, admin)

        response = client.get("/admin/users")

        assert response.status_code == 200, response.text


class TestListUsers:
    def test_includes_inactive_users(self, client, session: Session) -> None:
        admin = make_user(session, email="admin2@example.com", is_admin=True)
        active_user = make_user(session, email="active@example.com", is_active=True)
        inactive_user = make_user(
            session, email="inactive@example.com", is_active=False
        )
        authenticate(client, admin)

        response = client.get("/admin/users")

        assert response.status_code == 200, response.text
        emails = {row["email"] for row in response.json()}
        assert active_user.email in emails
        assert inactive_user.email in emails
        inactive_row = next(
            row for row in response.json() if row["email"] == inactive_user.email
        )
        assert inactive_row["is_active"] is False


class TestListHouseholds:
    def test_returns_owner_for_owned_household_and_null_for_unowned(
        self, client, session: Session
    ) -> None:
        admin = make_user(session, email="admin3@example.com", is_admin=True)
        owner = make_user(session, email="owner3@example.com")
        owned = make_household(session, name="Owned Plot", user_id=owner.id)
        unowned = make_household(session, name="Unowned Plot", user_id=None)
        authenticate(client, admin)

        response = client.get("/admin/households")

        assert response.status_code == 200, response.text
        by_id = {row["id"]: row for row in response.json()}
        assert by_id[owned.id]["owner"]["id"] == owner.id
        assert by_id[owned.id]["owner"]["email"] == owner.email
        assert by_id[unowned.id]["owner"] is None
        assert by_id[unowned.id]["user_id"] is None


def test_summed_usage_kwh_handles_missing_values() -> None:
    assert _summed_usage_kwh(None) is None
    assert _summed_usage_kwh(Decimal("10.00"), Decimal("5.50")) == Decimal("15.50")
    assert _summed_usage_kwh(Decimal("0"), None) == Decimal("0")


class TestAdminDashboard:
    def test_returns_submission_status_and_latest_reading(
        self, client, session: Session
    ) -> None:
        admin = make_user(session, email="dashboard-admin@example.com", is_admin=True)
        owner = make_user(session, email="dashboard-owner@example.com")
        submitted = make_household(session, name="Submitted Plot", user_id=owner.id)
        make_household(session, name="Missing Plot", user_id=None)
        make_meter_reading(
            session,
            household_id=submitted.id,
            period="2026-07",
            day_usage_kwh="10.00",
            night_usage_kwh="5.00",
            amount_charged_uah="50.25",
        )
        make_meter_reading(
            session,
            household_id=submitted.id,
            period="2026-08",
            day_usage_kwh="12.00",
            night_usage_kwh="6.00",
            amount_charged_uah="60.30",
        )
        authenticate(client, admin)

        response = client.get("/admin/dashboard")

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["current_period"] == "2026-08"
        by_name = {row["name"]: row for row in body["households"]}
        assert by_name["Submitted Plot"]["submission_status"] == "submitted"
        assert by_name["Submitted Plot"]["latest_period"] == "2026-08"
        assert by_name["Submitted Plot"]["latest_usage_kwh"] == "18.00"
        assert by_name["Submitted Plot"]["latest_amount_charged_uah"] == "60.30"
        assert by_name["Submitted Plot"]["owner"]["id"] == owner.id
        assert by_name["Missing Plot"]["submission_status"] == "missing"
        assert by_name["Missing Plot"]["latest_period"] is None
        assert by_name["Missing Plot"]["owner"] is None

    def test_includes_household_with_no_current_period_reading(
        self, client, session: Session
    ) -> None:
        admin = make_user(session, email="dashboard-admin2@example.com", is_admin=True)
        household = make_household(session, name="Older Reading Plot", user_id=admin.id)
        make_meter_reading(
            session, household_id=household.id, period="2026-07", day_usage_kwh="4.00"
        )
        authenticate(client, admin)

        response = client.get("/admin/dashboard")

        assert response.status_code == 200, response.text
        row = next(
            item for item in response.json()["households"] if item["id"] == household.id
        )
        assert row["submission_status"] == "missing"
        assert row["latest_period"] == "2026-07"
        assert row["latest_usage_kwh"] == "4.00"


class TestCreateHousehold:
    def test_nonexistent_user_id_is_not_found(self, client, session: Session) -> None:
        admin = make_user(session, email="admin4@example.com", is_admin=True)
        authenticate(client, admin)

        response = client.post(
            "/admin/households", json={"name": "New Plot", "user_id": 999_999}
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "userNotFound"

    def test_inactive_user_is_conflict(self, client, session: Session) -> None:
        admin = make_user(session, email="admin5@example.com", is_admin=True)
        inactive_user = make_user(
            session, email="inactive2@example.com", is_active=False
        )
        authenticate(client, admin)

        response = client.post(
            "/admin/households",
            json={"name": "New Plot", "user_id": inactive_user.id},
        )

        assert response.status_code == 409
        assert response.json()["detail"] == "userInactive"

    def test_success_creates_household_with_owner(
        self, client, session: Session
    ) -> None:
        admin = make_user(session, email="admin6@example.com", is_admin=True)
        new_owner = make_user(session, email="newowner@example.com")
        authenticate(client, admin)

        response = client.post(
            "/admin/households",
            json={"name": "Fresh Plot", "user_id": new_owner.id},
        )

        assert response.status_code == 201, response.text
        body = response.json()
        assert body["name"] == "Fresh Plot"
        assert body["user_id"] == new_owner.id
        assert body["owner"]["id"] == new_owner.id
        assert body["owner"]["email"] == new_owner.email


class TestAssignHouseholdOwner:
    def test_nonexistent_household_is_not_found(self, client, session: Session) -> None:
        admin = make_user(session, email="admin7@example.com", is_admin=True)
        user = make_user(session, email="target1@example.com")
        authenticate(client, admin)

        response = client.patch(
            "/admin/households/999999/owner", json={"user_id": user.id}
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "householdNotFound"

    def test_nonexistent_user_id_is_not_found(self, client, session: Session) -> None:
        admin = make_user(session, email="admin8@example.com", is_admin=True)
        household = make_household(session, name="Plot A", user_id=None)
        authenticate(client, admin)

        response = client.patch(
            f"/admin/households/{household.id}/owner",
            json={"user_id": 999999},
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "userNotFound"

    def test_inactive_user_is_conflict(self, client, session: Session) -> None:
        admin = make_user(session, email="admin9@example.com", is_admin=True)
        household = make_household(session, name="Plot B", user_id=None)
        inactive_user = make_user(
            session, email="inactive3@example.com", is_active=False
        )
        authenticate(client, admin)

        response = client.patch(
            f"/admin/households/{household.id}/owner",
            json={"user_id": inactive_user.id},
        )

        assert response.status_code == 409
        assert response.json()["detail"] == "userInactive"

    def test_reassigning_owned_household_without_confirmation_is_conflict(
        self, client, session: Session
    ) -> None:
        admin = make_user(session, email="admin10@example.com", is_admin=True)
        original_owner = make_user(session, email="original@example.com")
        new_owner = make_user(session, email="newtarget@example.com")
        household = make_household(session, name="Plot C", user_id=original_owner.id)
        authenticate(client, admin)

        response = client.patch(
            f"/admin/households/{household.id}/owner",
            json={"user_id": new_owner.id},
        )

        assert response.status_code == 409
        assert response.json()["detail"] == "householdAlreadyAssigned"

    def test_reassigning_owned_household_with_confirmation_succeeds(
        self, client, session: Session
    ) -> None:
        admin = make_user(session, email="admin11@example.com", is_admin=True)
        original_owner = make_user(session, email="original2@example.com")
        new_owner = make_user(session, email="newtarget2@example.com")
        household = make_household(session, name="Plot D", user_id=original_owner.id)
        authenticate(client, admin)

        response = client.patch(
            f"/admin/households/{household.id}/owner",
            json={"user_id": new_owner.id, "confirm_reassignment": True},
        )

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["user_id"] == new_owner.id
        assert body["owner"]["id"] == new_owner.id

    def test_unassigning_owned_household_without_confirmation_is_conflict(
        self, client, session: Session
    ) -> None:
        """Regression guard: unassignment (user_id: null) is a reassignment too.

        Previously `is_reassignment` only triggered when both the old and new
        owner were non-null, so setting `user_id: null` on an owned household
        silently unassigned it without the confirmation the UI is supposed to
        force.
        """
        admin = make_user(session, email="admin12@example.com", is_admin=True)
        original_owner = make_user(session, email="original3@example.com")
        household = make_household(session, name="Plot E", user_id=original_owner.id)
        authenticate(client, admin)

        response = client.patch(
            f"/admin/households/{household.id}/owner",
            json={"user_id": None},
        )

        assert response.status_code == 409
        assert response.json()["detail"] == "householdAlreadyAssigned"

    def test_unassigning_owned_household_with_confirmation_succeeds(
        self, client, session: Session
    ) -> None:
        admin = make_user(session, email="admin13@example.com", is_admin=True)
        original_owner = make_user(session, email="original4@example.com")
        household = make_household(session, name="Plot F", user_id=original_owner.id)
        authenticate(client, admin)

        response = client.patch(
            f"/admin/households/{household.id}/owner",
            json={"user_id": None, "confirm_reassignment": True},
        )

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["user_id"] is None
        assert body["owner"] is None

    def test_assigning_first_time_owner_succeeds_without_confirmation(
        self, client, session: Session
    ) -> None:
        admin = make_user(session, email="admin14@example.com", is_admin=True)
        new_owner = make_user(session, email="firsttime@example.com")
        household = make_household(session, name="Plot G", user_id=None)
        authenticate(client, admin)

        response = client.patch(
            f"/admin/households/{household.id}/owner",
            json={"user_id": new_owner.id},
        )

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["user_id"] == new_owner.id
        assert body["owner"]["id"] == new_owner.id
