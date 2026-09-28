"""Coverage for Kyiv-local billing period/window computation (issue #141).

`current_billing_period` and `is_submission_window_open` used to derive the
"current month" from server UTC. Around midnight Kyiv time on the 1st/6th
that disagrees with the Kyiv calendar date a resident is actually looking
at -- the tests below construct explicit tz-aware instants (including ones
whose UTC calendar day differs from their Kyiv calendar day) to pin the
Kyiv-based behavior at exactly those boundaries.
"""

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from app.core.domain import (
    current_billing_period,
    is_submission_window_open,
    submission_window,
)
from sqlmodel import Session
from tests.factories import authenticate, make_user

KYIV = ZoneInfo("Europe/Kyiv")


class TestCurrentBillingPeriodAndWindowBoundaries:
    def test_23_59_59_kyiv_on_day_1_is_still_in_the_prior_months_window(self) -> None:
        # July 1, 23:59:59 Kyiv: residents are submitting for June, and the
        # window (which opened at July 1 00:00:00) is still open.
        now = datetime(2026, 7, 1, 23, 59, 59, tzinfo=KYIV)

        assert current_billing_period(now) == "2026-06"
        assert is_submission_window_open(now)

    def test_window_opens_at_the_first_instant_of_day_1_kyiv(self) -> None:
        now = datetime(2026, 7, 1, 0, 0, 0, tzinfo=KYIV)

        assert current_billing_period(now) == "2026-06"
        assert is_submission_window_open(now)

    def test_window_is_closed_one_second_before_it_opens(self) -> None:
        # 23:59:59 Kyiv on June 30 -- one second before July's window opens.
        now = datetime(2026, 6, 30, 23, 59, 59, tzinfo=KYIV)

        assert not is_submission_window_open(now)

    def test_window_is_open_at_its_very_last_instant_on_day_5(self) -> None:
        now = datetime(2026, 7, 5, 23, 59, 59, 999999, tzinfo=KYIV)

        assert is_submission_window_open(now)

    def test_window_is_closed_at_the_first_instant_of_day_6(self) -> None:
        now = datetime(2026, 7, 6, 0, 0, 0, tzinfo=KYIV)

        assert not is_submission_window_open(now)

    def test_a_utc_instant_that_is_already_the_next_kyiv_calendar_day_uses_kyiv_date(
        self,
    ) -> None:
        # 2026-07-05 22:30 UTC is, in Kyiv (UTC+3 in July, EEST), already
        # 2026-07-06 01:30 -- past the deadline. Code that used the UTC
        # calendar date instead of Kyiv's would wrongly report the window as
        # still open (and the wrong period as "current"); this is the actual
        # bug behind issue #141.
        now = datetime(2026, 7, 5, 22, 30, 0, tzinfo=timezone.utc)

        assert now.astimezone(KYIV).day == 6
        assert not is_submission_window_open(now)

    def test_a_utc_instant_still_on_day_1_kyiv_despite_being_day_0_utc_calendar(
        self,
    ) -> None:
        # 2026-06-30 22:00 UTC is 2026-07-01 01:00 in Kyiv (EEST, +3) -- the
        # window has already opened in Kyiv even though the UTC calendar date
        # is still June 30.
        now = datetime(2026, 6, 30, 22, 0, 0, tzinfo=timezone.utc)

        assert now.astimezone(KYIV).day == 1
        assert current_billing_period(now) == "2026-06"
        assert is_submission_window_open(now)


class TestSubmissionWindowShape:
    def test_returns_kyiv_aware_bounds_for_the_reference_months_window(self) -> None:
        now = datetime(2026, 7, 3, 12, 0, 0, tzinfo=KYIV)

        opens_at, closes_at = submission_window(now)

        assert opens_at == datetime(2026, 7, 1, 0, 0, 0, tzinfo=KYIV)
        assert closes_at == datetime(2026, 7, 5, 23, 59, 59, 999999, tzinfo=KYIV)


class TestDstAcrossTheKyivTimezoneDatabase:
    """Ukraine currently observes EET (UTC+2) / EEST (UTC+3) DST via zoneinfo.

    Empirically (see the offsets asserted below), the spring-forward and
    fall-back transitions land on the last Sunday of March and October --
    both well after day 5, so no submission window (day 1-5) actually spans
    a transition instant. This test doesn't (and can't honestly) exercise a
    DST-crossing *boundary* in the deadline logic; instead it pins that
    zoneinfo is in fact applying the seasonal offset the rest of these tests
    implicitly rely on, and that the two neighboring windows (open just
    before, and just after, a transition) each still resolve with the
    correct local offset.
    """

    def test_kyiv_utcoffset_is_plus_2_in_winter_and_plus_3_in_summer(self) -> None:
        winter = datetime(2026, 1, 15, tzinfo=KYIV)
        summer = datetime(2026, 7, 15, tzinfo=KYIV)

        assert winter.utcoffset() == timedelta(hours=2)
        assert summer.utcoffset() == timedelta(hours=3)

    def test_the_march_transition_falls_after_the_march_submission_window(self) -> None:
        # Confirms the window (day 1-5) can never straddle this transition,
        # so is_submission_window_open never needs to compare across a DST
        # change within a single window.
        after_transition = datetime(
            2026, 3, 29, 4, 0, 0, tzinfo=timezone.utc
        ).astimezone(KYIV)
        assert after_transition.utcoffset() == timedelta(hours=3)
        before = datetime(2026, 3, 28, 3, 0, 0, tzinfo=KYIV)
        assert before.utcoffset() == timedelta(hours=2)
        transition = after_transition

        march_window_closes = submission_window(datetime(2026, 3, 3, tzinfo=KYIV))[1]
        assert march_window_closes < transition

    def test_windows_immediately_before_and_after_the_october_transition_both_resolve(
        self,
    ) -> None:
        # October's window (opens Oct 1) is entirely before the late-October
        # transition; November's (opens Nov 1) is entirely after it. Each
        # must still compute the correct Kyiv-local bounds under its own
        # offset.
        october_open = datetime(2026, 10, 3, 12, 0, 0, tzinfo=KYIV)
        november_open = datetime(2026, 11, 3, 12, 0, 0, tzinfo=KYIV)

        assert october_open.utcoffset() == timedelta(hours=3)
        assert november_open.utcoffset() == timedelta(hours=2)
        assert is_submission_window_open(october_open)
        assert is_submission_window_open(november_open)


class TestGetBillingWindowRoute:
    def test_requires_authentication(self, client) -> None:
        response = client.get("/billing/window")

        assert response.status_code == 401

    def test_returns_the_live_window_matching_the_domain_functions(
        self, client, session: Session
    ) -> None:
        user = make_user(session)
        authenticate(client, user)

        response = client.get("/billing/window")

        assert response.status_code == 200, response.text
        body = response.json()

        assert body["period"] == current_billing_period()
        assert body["is_open"] == is_submission_window_open()

        expected_opens_at, expected_closes_at = submission_window()
        assert datetime.fromisoformat(
            body["opens_at"].replace("Z", "+00:00")
        ) == expected_opens_at.astimezone(timezone.utc)
        assert datetime.fromisoformat(
            body["closes_at"].replace("Z", "+00:00")
        ) == expected_closes_at.astimezone(timezone.utc)
