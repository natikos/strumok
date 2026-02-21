from pydantic import BaseModel, Field


class RegisterIn(BaseModel):
    email: str = Field(min_length=5, max_length=255)
    first_name: str = Field(min_length=2, max_length=255)
    last_name: str = Field(min_length=2, max_length=255)
    password: str = Field(min_length=8, max_length=128)


class LoginIn(BaseModel):
    email: str = Field(min_length=5, max_length=255)
    password: str = Field(min_length=1, max_length=128)


class UserOut(BaseModel):
    id: int
    email: str
    first_name: str
    last_name: str
    is_admin: bool
    is_active: bool


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
