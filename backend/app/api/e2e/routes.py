from fastapi import APIRouter, Depends, Response, status
from sqlmodel import Session

from app.api.e2e import service
from app.api.e2e.schemas import (
    ClockIn,
    ClockOut,
    E2eUserIn,
    E2eUserOut,
    OutboxEmailOut,
)
from app.db import get_session

# Kept out of the OpenAPI schema so it never reaches the generated frontend types.
router = APIRouter(prefix="/__e2e", tags=["e2e"], include_in_schema=False)


@router.post("/reset", status_code=status.HTTP_204_NO_CONTENT)
def reset(session: Session = Depends(get_session)) -> Response:
    service.reset(session)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put("/clock", response_model=ClockOut)
def set_clock(payload: ClockIn) -> ClockOut:
    return ClockOut(now=service.set_clock(payload.now))


@router.delete("/clock", status_code=status.HTTP_204_NO_CONTENT)
def reset_clock() -> Response:
    service.reset_clock()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/users", response_model=E2eUserOut, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: E2eUserIn, session: Session = Depends(get_session)
) -> E2eUserOut:
    user = service.create_user(
        session,
        email_address=payload.email,
        password=payload.password,
        first_name=payload.first_name,
        last_name=payload.last_name,
        is_admin=payload.is_admin,
        language=payload.language,
    )
    return E2eUserOut(id=user.id, email=user.email)


@router.get("/outbox", response_model=list[OutboxEmailOut])
def read_outbox(to: str | None = None) -> list[OutboxEmailOut]:
    return [OutboxEmailOut(**message) for message in service.outbox(to)]
