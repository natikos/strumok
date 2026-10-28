from collections.abc import Sequence
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.core.config import settings
from app.core.time import utc_now
from app.db.models import LanguageCode, ThemeMode, User


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class VerifyEmailIn(BaseModel):
    token: str = Field(min_length=1, max_length=2048)


class ChangePasswordIn(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class ChangeEmailIn(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_email: EmailStr


class PasswordResetRequestIn(BaseModel):
    email: EmailStr


class PasswordResetConfirmIn(BaseModel):
    token: str = Field(min_length=1, max_length=2048)
    password: str = Field(min_length=8, max_length=128)


class HouseholdSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    first_name: str
    last_name: str
    is_admin: bool
    is_active: bool
    email_verified: bool
    verification_email_retry_after_seconds: int
    theme: ThemeMode
    language: LanguageCode
    reminder_hour: int

    @classmethod
    def from_user(cls, user: User) -> "UserOut":
        retry_after_seconds = 0
        last_sent_at = user.verification_email_last_sent_at
        cooldown_seconds = settings.auth.verify_email_resend_cooldown_seconds

        if last_sent_at is not None and not user.email_verified:
            elapsed_seconds = int((utc_now() - last_sent_at).total_seconds())
            retry_after_seconds = max(cooldown_seconds - elapsed_seconds, 0)

        return cls.model_validate(
            {
                **user.model_dump(),
                "verification_email_retry_after_seconds": retry_after_seconds,
            }
        )


class UserWithHouseholdsOut(UserOut):
    households: list[HouseholdSummary]

    @classmethod
    def from_user_with_households(
        cls, user: User, *, households: Sequence[Any]
    ) -> "UserWithHouseholdsOut":
        base = UserOut.from_user(user)
        return cls.model_validate(
            {
                **base.model_dump(),
                "households": [HouseholdSummary.model_validate(h) for h in households],
            }
        )


class UserPreferencesIn(BaseModel):
    theme: ThemeMode | None = None
    language: LanguageCode | None = None
    reminder_hour: int | None = Field(
        default=None, ge=0, le=23, description="Hour of day, Europe/Kyiv"
    )


class ErrorOut(BaseModel):
    detail: str
