import re
from functools import lru_cache
from typing import Annotated, Literal

from pydantic import SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict
from sqlalchemy.engine import make_url


class DbSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="DATABASE_",
        extra="ignore",
        env_file=".env",
        hide_input_in_errors=True,
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
        hide_input_in_errors=True,
    )

    secret_key: SecretStr
    algorithm: str = "HS256"
    access_token_expiration: int = 60  # (min) 1 hour -- refreshed via /auth/refresh
    auth_cookie_name: str = "access_token"
    verify_email_resend_cooldown_seconds: int = 180  # 3 minutes
    verification_token_expiration: int = 60  # (min) 1 hour
    refresh_absolute_window_days: int = 180  # (days) hard session cap since login


class BrevoSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="BREVO_",
        extra="ignore",
        env_file=".env",
        hide_input_in_errors=True,
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
        hide_input_in_errors=True,
    )

    vapid_public_key: str
    vapid_private_key: SecretStr
    vapid_subject: str


class ImapSettings(BaseSettings):
    """Mailbox the accountant's statement is emailed to. Ingest stays off
    until the user, app password and at least one allowed sender are set."""

    model_config = SettingsConfigDict(
        env_prefix="IMAP_",
        extra="ignore",
        env_file=".env",
        hide_input_in_errors=True,
    )

    host: str = "imap.gmail.com"
    user: str = ""
    password: SecretStr = SecretStr("")
    folder: str = "INBOX"
    # Whose Authentication-Results header is trusted: the receiving server.
    authserv_id: str = "mx.google.com"
    allowed_senders: Annotated[list[str], NoDecode] = []

    @field_validator("allowed_senders", mode="before")
    @classmethod
    def parse_allowed_senders(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            return [s.strip().lower() for s in value.split(",") if s.strip()]
        return [s.lower() for s in value]

    @property
    def enabled(self) -> bool:
        return bool(
            self.user and self.password.get_secret_value() and self.allowed_senders
        )


E2E_DATABASE_HOSTS = {"localhost", "127.0.0.1"}


# libpq reads these from the query string too, so any of them could point a
# URL that looks local at another server.
CONNECTION_QUERY_KEYS = {"host", "hostaddr", "service"}
E2E_DATABASE_NAME = re.compile(r"[a-z0-9_]+_e2e")


def is_e2e_database(url: str) -> bool:
    """A throwaway e2e database: local host, a plain name ending in `_e2e`, and
    nothing in the query string that could redirect the connection."""
    parsed = make_url(url)
    return (
        parsed.host in E2E_DATABASE_HOSTS
        and E2E_DATABASE_NAME.fullmatch(parsed.database or "") is not None
        and not CONNECTION_QUERY_KEYS & set(parsed.query)
    )


class Settings(BaseSettings):
    """Application-wide grouped configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        # A failed validation would otherwise print the whole input, which
        # holds every secret read from .env.
        hide_input_in_errors=True,
    )

    # `e2e` is only for the Playwright suite (docs/testing.md): it shifts the
    # app clock and mounts test-only routes, so it refuses any database that
    # isn't a local `*_e2e` one. Never set it in production.
    environment: Literal["development", "production", "e2e"]
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
    imap: ImapSettings = ImapSettings()

    @model_validator(mode="after")
    def guard_e2e(self) -> "Settings":
        if self.environment != "e2e":
            return self
        if not is_e2e_database(self.db.url):
            raise ValueError(
                "ENVIRONMENT=e2e needs a local database whose name ends in _e2e"
            )
        if self.imap.enabled:
            raise ValueError("ENVIRONMENT=e2e must not have IMAP configured")
        return self

    @property
    def auth_cookie_secure(self) -> bool:
        return self.environment != "development"

    @property
    def auth_token_ttl_seconds(self) -> int:
        """Cookie max_age: the full session cap, not the short JWT lifetime."""
        return self.auth.refresh_absolute_window_days * 24 * 60 * 60


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore


settings: Settings = get_settings()
