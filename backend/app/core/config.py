from functools import lru_cache
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class DbSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="DB_",
        extra="ignore",
        env_file=".env",
    )

    url: str


class AuthSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="AUTH_",
        extra="ignore",
        env_file=".env",
    )

    secret_key: str
    algorithm: str = "HS256"
    access_token_expiration: int = 1440  # (min) 24 hours
    auth_cookie_name: str = "access_token"


class Settings(BaseSettings):
    """Application-wide grouped configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )

    environment: str = "development"
    app_name: str = "Strumok"
    app_port: int = 8000
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:5173"]

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    db: DbSettings = DbSettings()  # type: ignore
    auth: AuthSettings = AuthSettings()  # type: ignore

    @property
    def auth_cookie_secure(self) -> bool:
        return self.environment != "development"

    @property
    def auth_token_ttl_seconds(self) -> int:
        return self.auth.access_token_expiration * 60


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings: Settings = get_settings()
