from pydantic import BaseModel, ConfigDict, field_validator


def _require_https_endpoint(value: str) -> str:
    if not value.startswith("https://"):
        raise ValueError("endpoint must be an https:// URL")
    return value


class PushSubscriptionKeysIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    p256dh: str
    auth: str


class PushSubscriptionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    endpoint: str
    keys: PushSubscriptionKeysIn

    _validate_endpoint = field_validator("endpoint")(_require_https_endpoint)


class PushUnsubscribeIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    endpoint: str

    _validate_endpoint = field_validator("endpoint")(_require_https_endpoint)


class VapidPublicKeyOut(BaseModel):
    public_key: str


class SendRemindersOut(BaseModel):
    sent: int
    removed: int
