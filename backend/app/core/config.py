from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


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


class Settings(BaseSettings):
    """Application-wide grouped configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )

    environment: str = "development"
    app_name: str = "Strumok"
    app_port: int = 8000
    cors_origins: str = "http://localhost:5173"

    db: DbSettings = DbSettings()  # type: ignore
    auth: AuthSettings = AuthSettings()  # type: ignore


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings: Settings = get_settings()
