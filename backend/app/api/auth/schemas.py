from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.core.config import settings
from app.core.time import utc_now
from app.db.models import LanguageCode, ThemeMode, User


class RegisterIn(BaseModel):
    email: EmailStr
    first_name: str = Field(min_length=2, max_length=255)
    last_name: str = Field(min_length=2, max_length=255)
    password: str = Field(min_length=8, max_length=128)


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


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


class UserPreferencesIn(BaseModel):
    theme: ThemeMode | None = None
    language: LanguageCode | None = None


class ErrorOut(BaseModel):
    detail: str
