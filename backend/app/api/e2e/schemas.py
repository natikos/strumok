from datetime import datetime

from pydantic import AwareDatetime, BaseModel, ConfigDict, EmailStr, Field

from app.db.models import LanguageCode


class ClockIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Tz-aware, so "day 2 at noon in Kyiv" can't be misread as UTC.
    now: AwareDatetime


class ClockOut(BaseModel):
    now: datetime


class E2eUserIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: str = Field(min_length=8)
    first_name: str = "E2e"
    last_name: str = "User"
    is_admin: bool = False
    language: LanguageCode = LanguageCode.EN


class E2eUserOut(BaseModel):
    id: int
    email: str


class OutboxEmailOut(BaseModel):
    to: str
    subject: str
    html_content: str
