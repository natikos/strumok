from functools import lru_cache
from typing import Annotated, Literal

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class DbSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="DATABASE_",
        extra="ignore",
        env_file=".env",
    )

    url: str

    @field_validator("url", mode="after")
    @classmethod
    def add_psycopg_driver(cls, value: str) -> str:
        if value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+psycopg://", 1)
        return value


class AuthSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="AUTH_",
        extra="ignore",
        env_file=".env",
    )

    secret_key: SecretStr
    algorithm: str = "HS256"
    access_token_expiration: int = 60  # (min) 1 hour -- refreshed via /auth/refresh
    auth_cookie_name: str = "access_token"
    verify_email_resend_cooldown_seconds: int = 180  # 3 minutes
    verification_token_expiration: int = 60  # (min) 1 hour
    internal_secret: SecretStr  # API secret for internal endpoints (push notifications, webhooks, cron jobs, etc.)
    # /auth/refresh accepts a token whose *exp* is this stale at most -- an
    # honest resident who opens the app once a month stays signed in.
    refresh_idle_window_days: int = 45
    # /auth/refresh accepts a token at most this long after the original
    # login (auth_time), even if refreshed continuously -- a hard session cap
    # independent of activity.
    refresh_absolute_window_days: int = 180


class BrevoSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="BREVO_",
        extra="ignore",
        env_file=".env",
    )

    api_key: SecretStr = SecretStr("")
    sender_email: str = ""
    sender_name: str = "Струмок (Електроенергія)"
    app_base_url: str = "http://localhost:5173"


class PushSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="PUSH_",
        extra="ignore",
        env_file=".env",
    )

    vapid_public_key: str
    vapid_private_key: SecretStr
    vapid_subject: str


class Settings(BaseSettings):
    """Application-wide grouped configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )

    environment: Literal["development", "production"]
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
    brevo: BrevoSettings = BrevoSettings()
    push: PushSettings = PushSettings()  # type: ignore

    @property
    def auth_cookie_secure(self) -> bool:
        return self.environment != "development"

    @property
    def auth_token_ttl_seconds(self) -> int:
        """Cookie max_age: must cover the whole possible session window (up
        to the absolute cap), not the short-lived JWT's own exp -- otherwise
        the cookie is gone long before an idle-but-still-valid session would
        refresh. The idle window is what actually cuts a stale session off;
        this is just how long the browser is asked to hold the cookie."""
        return self.auth.refresh_absolute_window_days * 24 * 60 * 60


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings: Settings = get_settings()
