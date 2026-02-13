from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserRegister(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=255)
    password: str = Field(min_length=8, max_length=128)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    full_name: str
    is_admin: bool


class ReadingCreate(BaseModel):
    meter_value: float = Field(ge=0)


class ReadingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    period: str
    meter_value: float
    usage: float
    submitted_at: datetime


class ReadingAdminOut(BaseModel):
    id: int
    period: str
    meter_value: float
    usage: float
    submitted_at: datetime
    user_id: int
    user_email: EmailStr
    user_full_name: str
