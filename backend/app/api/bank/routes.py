import logging
from typing import Any

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Response,
    UploadFile,
    status,
)
from fastapi.responses import JSONResponse
from sqlmodel import Session

from app.api.auth.schemas import ErrorOut
from app.api.bank import review
from app.api.bank.matching import suggest_households
from app.api.bank.schemas import (
    BankStatementErrorOut,
    BankTransactionOut,
    ConfirmedPaymentOut,
    ConfirmIn,
    LinkCandidateOut,
    LinkIn,
    StatementImportOut,
    SuggestionOut,
)
from app.api.bank.service import (
    MAX_BYTES,
    BankStatementError,
    PaymentDetailsMissingError,
    StatementNotCsvError,
    StatementTooLargeError,
    import_statement,
)
from app.api.deps import require_admin
from app.api.push.billing_notifications import notify_bank_queue, notify_shortfall
from app.db import get_session
from app.db.models import User

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/admin/bank-statements",
    tags=["bank"],
    dependencies=[Depends(require_admin)],
)

CurrentAdmin = Depends(require_admin)

_UPLOAD_RESPONSES: dict[int | str, dict[str, Any]] = {
    413: {
        "description": "File is larger than 1 MB",
        "model": ErrorOut,
        "content": {
            "application/json": {"example": {"detail": "bankStatementTooLarge"}}
        },
    },
    422: {
        "description": (
            "Not a .csv, no payment details set, or the statement cannot be "
            "imported (row and column name the offending cell, never its value). "
            "Codes: bankStatementNotCsv, paymentDetailsMissing, "
            "bankStatementInvalid, bankStatementTooManyRows, "
            "bankStatementWrongAccount"
        ),
        "model": BankStatementErrorOut,
        "content": {
            "application/json": {
                "example": {
                    "detail": "bankStatementInvalid",
                    "row": 2,
                    "column": "Сума",
                }
            }
        },
    },
}


@router.post("", response_model=StatementImportOut, responses=_UPLOAD_RESPONSES)
def upload_statement(
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
    admin: User = CurrentAdmin,
) -> StatementImportOut:
    # One byte over the cap is enough to know it is too big, without reading
    # an arbitrarily large body into memory.
    data = file.file.read(MAX_BYTES + 1)
    try:
        result = import_statement(
            session,
            actor_id=admin.id,
            filename=file.filename or "",
            data=data,
        )
    except StatementTooLargeError as exc:
        raise HTTPException(status_code=413, detail="bankStatementTooLarge") from exc
    except PaymentDetailsMissingError as exc:
        raise HTTPException(status_code=422, detail="paymentDetailsMissing") from exc
    except StatementNotCsvError as exc:
        raise HTTPException(status_code=422, detail="bankStatementNotCsv") from exc
    except BankStatementError as exc:
        return JSONResponse(
            status_code=422,
            content={"detail": exc.code, "row": exc.row, "column": exc.column},
        )  # type: ignore[return-value]

    if result.credits_new:
        try:
            notify_bank_queue(session=session, file_id=result.file_id)
        except Exception:
            logger.exception("Bank queue notification failed")
    _notify_shortfall_safely(session)
    return StatementImportOut(
        already_imported=result.already_imported,
        credits_new=result.credits_new,
        credits_duplicate=result.credits_duplicate,
        debits_skipped=result.debits_skipped,
        covered_through=result.covered_through,
    )


def _notify_shortfall_safely(session: Session) -> None:
    """Runs after the change has committed: clearing the last queued credit
    is what can finally open the shortfall window."""
    try:
        notify_shortfall(session=session)
    except Exception:
        logger.exception("Shortfall notification failed")


review_router = APIRouter(
    prefix="/admin/bank-transactions",
    tags=["bank"],
    dependencies=[Depends(require_admin)],
)


def _error(code: int, *details: str) -> dict[str, Any]:
    return {
        "description": ", ".join(details),
        "model": ErrorOut,
        "content": {
            "application/json": {
                "examples": {d: {"value": {"detail": d}} for d in details}
            }
        },
    }


_RESOLVE_RESPONSES: dict[int | str, dict[str, Any]] = {
    404: _error(404, "bankTransactionNotFound", "householdNotFound"),
    409: _error(409, "bankTransactionResolved"),
}


@review_router.get("", response_model=list[BankTransactionOut])
def list_queue(session: Session = Depends(get_session)) -> list[BankTransactionOut]:
    items = review.list_queue(session)
    suggestions = suggest_households(session, [i.transaction for i in items])
    return [
        BankTransactionOut(
            id=item.transaction.id,
            operation_date=item.transaction.operation_date,
            amount_uah=item.transaction.amount_uah,
            payer_name=item.transaction.payer_name,
            purpose=item.transaction.purpose,
            suggested_household_id=found[0].household_id if found else None,
            suggestion_source=found[0].source if found else None,
            suggestions=[
                SuggestionOut(household_id=s.household_id, source=s.source)
                for s in found
            ],
            link_candidates=[
                LinkCandidateOut(
                    payment_id=p.id, household_id=p.household_id, paid_on=p.paid_on
                )
                for p in item.link_candidates
            ],
        )
        for item, found in zip(items, suggestions)
    ]


@review_router.post(
    "/{transaction_id}/confirm",
    response_model=list[ConfirmedPaymentOut],
    responses={
        **_RESOLVE_RESPONSES,
        422: _error(422, "splitInvalid", "beforeOpeningBalance"),
    },
)
def confirm_transaction(
    transaction_id: int,
    payload: ConfirmIn,
    session: Session = Depends(get_session),
    admin: User = CurrentAdmin,
) -> list[ConfirmedPaymentOut]:
    try:
        payments = review.confirm(
            session,
            transaction_id=transaction_id,
            lines=[
                review.SplitLine(line.household_id, line.amount_uah)
                for line in payload.lines
            ],
            actor_id=admin.id,
        )
    except review.BankTransactionNotFoundError as exc:
        raise HTTPException(404, "bankTransactionNotFound") from exc
    except review.HouseholdNotFoundError as exc:
        raise HTTPException(404, "householdNotFound") from exc
    except review.BankTransactionResolvedError as exc:
        raise HTTPException(409, "bankTransactionResolved") from exc
    except review.SplitInvalidError as exc:
        raise HTTPException(422, "splitInvalid") from exc
    except review.BeforeOpeningBalanceError as exc:
        raise HTTPException(422, "beforeOpeningBalance") from exc
    _notify_shortfall_safely(session)
    return [
        ConfirmedPaymentOut(
            payment_id=p.id, household_id=p.household_id, amount_uah=p.amount_uah
        )
        for p in payments
    ]


@review_router.post(
    "/{transaction_id}/link",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        **_RESOLVE_RESPONSES,
        422: _error(422, "manualPaymentNotLinkable"),
    },
)
def link_transaction(
    transaction_id: int,
    payload: LinkIn,
    session: Session = Depends(get_session),
    admin: User = CurrentAdmin,
) -> Response:
    try:
        review.link(
            session,
            transaction_id=transaction_id,
            payment_id=payload.payment_id,
            actor_id=admin.id,
        )
    except review.BankTransactionNotFoundError as exc:
        raise HTTPException(404, "bankTransactionNotFound") from exc
    except review.BankTransactionResolvedError as exc:
        raise HTTPException(409, "bankTransactionResolved") from exc
    except review.ManualPaymentNotLinkableError as exc:
        raise HTTPException(422, "manualPaymentNotLinkable") from exc
    _notify_shortfall_safely(session)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@review_router.post(
    "/{transaction_id}/dismiss",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=_RESOLVE_RESPONSES,
)
def dismiss_transaction(
    transaction_id: int,
    session: Session = Depends(get_session),
    admin: User = CurrentAdmin,
) -> Response:
    try:
        review.dismiss(session, transaction_id=transaction_id, actor_id=admin.id)
    except review.BankTransactionNotFoundError as exc:
        raise HTTPException(404, "bankTransactionNotFound") from exc
    except review.BankTransactionResolvedError as exc:
        raise HTTPException(409, "bankTransactionResolved") from exc
    _notify_shortfall_safely(session)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
