from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from .auth import get_current_admin, get_current_user
from .database import get_db
from .models import Reading, User
from .schemas import ReadingAdminOut, ReadingCreate, ReadingOut

router = APIRouter(prefix="/api/readings", tags=["readings"])


def current_period() -> str:
    now = datetime.utcnow()
    return f"{now.year:04d}-{now.month:02d}"


def ensure_submission_window() -> None:
    day = datetime.utcnow().day
    if day < 1 or day > 5:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Readings can only be submitted from day 1 to day 5 of each month",
        )


@router.post("/submit", response_model=ReadingOut, status_code=status.HTTP_201_CREATED)
def submit_reading(
    payload: ReadingCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_submission_window()
    period = current_period()

    existing = db.scalar(
        select(Reading).where(and_(Reading.user_id == current_user.id, Reading.period == period))
    )
    if existing:
        raise HTTPException(status_code=409, detail="Reading for this month already submitted")

    previous = db.scalar(
        select(Reading)
        .where(Reading.user_id == current_user.id)
        .order_by(Reading.period.desc())
        .limit(1)
    )
    previous_value = previous.meter_value if previous else payload.meter_value
    usage = payload.meter_value - previous_value
    if usage < 0:
        raise HTTPException(status_code=400, detail="Meter value cannot be lower than previous")

    reading = Reading(
        user_id=current_user.id,
        period=period,
        meter_value=payload.meter_value,
        usage=usage,
    )
    db.add(reading)
    db.commit()
    db.refresh(reading)
    return reading


@router.get("/my", response_model=list[ReadingOut])
def my_readings(
    limit: int = Query(default=12, ge=1, le=120),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = db.scalars(
        select(Reading)
        .where(Reading.user_id == current_user.id)
        .order_by(Reading.period.desc())
        .limit(limit)
    ).all()
    return list(rows)


@router.get("/admin/all", response_model=list[ReadingAdminOut])
def all_readings(
    period: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}$"),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    query = (
        select(Reading, User)
        .join(User, User.id == Reading.user_id)
        .order_by(Reading.period.desc(), User.full_name.asc())
    )
    if period:
        query = query.where(Reading.period == period)

    result = db.execute(query).all()
    return [
        ReadingAdminOut(
            id=reading.id,
            period=reading.period,
            meter_value=reading.meter_value,
            usage=reading.usage,
            submitted_at=reading.submitted_at,
            user_id=user.id,
            user_email=user.email,
            user_full_name=user.full_name,
        )
        for reading, user in result
    ]
