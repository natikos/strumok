from pydantic import BaseModel, ConfigDict, EmailStr, Field

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
    theme: ThemeMode
    language: LanguageCode

    @classmethod
    def from_user(cls, user: User) -> "UserOut":
        return cls.model_validate(user)


class UserPreferencesIn(BaseModel):
    theme: ThemeMode | None = None
    language: LanguageCode | None = None


class ErrorOut(BaseModel):
    detail: str
