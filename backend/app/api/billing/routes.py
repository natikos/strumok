from fastapi import APIRouter, Depends
from sqlmodel import Session, col, select

from app.api.billing.bank_coverage import get_coverage, is_awaiting_statement
from app.api.billing.payment_details import get_payment_details
from app.api.billing.payments import get_balance
from app.api.billing.schemas import (
    AdjustmentOut,
    BalanceOut,
    BankCoverageOut,
    CurrentPeriodOut,
    HouseholdStatementsOut,
    PaymentDetailsOut,
    ShortfallOut,
    StatementLineOut,
)
from app.api.billing.shortfall import household_shortfall, settled_window
from app.api.billing.service import list_adjustments, list_statements
from app.api.deps import get_current_user
from app.core.domain import current_billing_period
from app.core.ownership import owner_scope
from app.db.models import BillingPeriod, Household, HouseholdOwnership, User
from app.api.meter_readings.routes import NO_HOUSEHOLD_RESPONSES, require_household_id
from app.db import get_session

router = APIRouter(
    prefix="/billing",
    tags=["billing"],
)


@router.get(
    "/statements",
    response_model=list[StatementLineOut],
    responses=NO_HOUSEHOLD_RESPONSES,
)
def get_my_statements(
    household_id: int = Depends(require_household_id),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> list[StatementLineOut]:
    return list_statements(
        session=session,
        household_id=household_id,
        owner_user_id=owner_scope(session, household_id, current_user.id),
    )


@router.get(
    "/adjustments",
    response_model=list[AdjustmentOut],
    responses=NO_HOUSEHOLD_RESPONSES,
)
def get_my_adjustments(
    household_id: int = Depends(require_household_id),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> list[AdjustmentOut]:
    return [
        AdjustmentOut.model_validate(a)
        for a in list_adjustments(
            session=session,
            household_id=household_id,
            owner_user_id=owner_scope(session, household_id, current_user.id),
        )
    ]


@router.get("/current-period", response_model=CurrentPeriodOut)
def get_current_period(
    session: Session = Depends(get_session),
) -> CurrentPeriodOut:
    period = current_billing_period()
    row = session.get(BillingPeriod, period)
    return CurrentPeriodOut(
        period=period, status="closed" if row and row.status == "closed" else "open"
    )


@router.get(
    "/balance",
    response_model=BalanceOut,
    responses=NO_HOUSEHOLD_RESPONSES,
)
def get_my_balance(
    household_id: int = Depends(require_household_id),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> BalanceOut:
    return BalanceOut.model_validate(
        get_balance(
            session=session,
            household_id=household_id,
            owner_user_id=owner_scope(session, household_id, current_user.id),
        ),
        from_attributes=True,
    )


@router.get(
    "/payment-details",
    response_model=PaymentDetailsOut | None,
    responses=NO_HOUSEHOLD_RESPONSES,
)
def get_my_payment_details(
    _household_id: int = Depends(require_household_id),
    session: Session = Depends(get_session),
) -> PaymentDetailsOut | None:
    row = get_payment_details(session)
    return PaymentDetailsOut.model_validate(row) if row else None


@router.get("/bank-coverage", response_model=BankCoverageOut)
def get_bank_coverage(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> BankCoverageOut:
    covered, uploaded = get_coverage(session)
    return BankCoverageOut(
        covered_through=covered,
        awaiting_statement=is_awaiting_statement(covered),
        last_imported_at=uploaded if current_user.is_admin else None,
    )


@router.get(
    "/shortfall",
    response_model=ShortfallOut,
    responses=NO_HOUSEHOLD_RESPONSES,
)
def get_my_shortfall(
    household_id: int = Depends(require_household_id),
    session: Session = Depends(get_session),
) -> ShortfallOut:
    window = settled_window(session)
    household = session.get(Household, household_id)
    if window is None or household is None:
        return ShortfallOut(active=False)
    owed = household_shortfall(session, window, household)
    if owed <= 0:
        return ShortfallOut(active=False)
    return ShortfallOut(active=True, due_date=window.due_date, owed_uah=owed)


me_router = APIRouter(prefix="/me", tags=["billing"])


@me_router.get("/statements", response_model=list[HouseholdStatementsOut])
def get_all_my_statements(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> list[HouseholdStatementsOut]:
    """Every household the user has owned, including ones handed over since:
    what they were billed, and what they still owe on each."""
    tenures = session.exec(
        select(HouseholdOwnership)
        .where(HouseholdOwnership.user_id == current_user.id)
        .order_by(col(HouseholdOwnership.valid_from))
    ).all()
    household_ids = {t.household_id for t in tenures} | set(
        session.exec(select(Household.id).where(Household.user_id == current_user.id))
    )
    earlier_owners = {
        (t.household_id, t.user_id, t.valid_from)
        for t in session.exec(
            select(HouseholdOwnership).where(
                col(HouseholdOwnership.household_id).in_(household_ids)
            )
        )
    }
    result = []
    for household in session.exec(
        select(Household).where(col(Household.id).in_(household_ids))
    ):
        is_current = household.user_id == current_user.id
        mine = [t for t in tenures if t.household_id == household.id]
        scope = owner_scope(session, household.id, current_user.id)
        result.append(
            HouseholdStatementsOut(
                household_id=household.id,
                household_name=household.name,
                is_current_owner=is_current,
                owned_since=mine[0].valid_from if mine else None,
                owned_until=None if is_current or not mine else mine[-1].valid_to,
                has_previous_owner=bool(mine)
                and any(
                    hid == household.id
                    and uid != current_user.id
                    and valid_from < mine[0].valid_from
                    for hid, uid, valid_from in earlier_owners
                ),
                balance=BalanceOut.model_validate(
                    get_balance(
                        session=session,
                        household_id=household.id,
                        owner_user_id=scope,
                    ),
                    from_attributes=True,
                ),
                statements=list_statements(
                    session=session,
                    household_id=household.id,
                    owner_user_id=scope,
                    include_provisional=is_current,
                ),
            )
        )
    return sorted(result, key=lambda r: (not r.is_current_owner, r.household_name))
