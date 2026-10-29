import logging
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from sqlmodel import Session

from app.api.auth.schemas import ErrorOut
from app.api.bank.schemas import BankStatementErrorOut, StatementImportOut
from app.api.bank.service import (
    MAX_BYTES,
    BankStatementError,
    PaymentDetailsMissingError,
    StatementNotCsvError,
    StatementTooLargeError,
    import_statement,
)
from app.api.deps import require_admin
from app.api.push.billing_notifications import notify_bank_queue
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
    return StatementImportOut(
        already_imported=result.already_imported,
        credits_new=result.credits_new,
        credits_duplicate=result.credits_duplicate,
        debits_skipped=result.debits_skipped,
        covered_through=result.covered_through,
    )
