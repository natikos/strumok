from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.orm import Session

from .auth import get_current_admin
from .database import get_db
from .models import User

router = APIRouter(prefix="/api/users", tags=["users"])


class PromotePayload(BaseModel):
    email: EmailStr


@router.post("/promote")
def promote_user(
    payload: PromotePayload,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    user = db.scalar(select(User).where(User.email == payload.email.lower()))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.is_admin = True
    db.commit()
    return {"message": f"{user.email} promoted to admin"}
