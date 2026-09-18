import secrets

from fastapi import Header, HTTPException, status

from app.core.config import settings

INTERNAL_SECRET_HEADER = "X-Internal-Secret"
INVALID_INTERNAL_SECRET_ERROR_CODE = "invalidInternalSecret"


def require_internal_secret(
    x_internal_secret: str | None = Header(default=None, alias=INTERNAL_SECRET_HEADER),
) -> None:
    expected = settings.push.reminder_secret.get_secret_value()
    if (
        not expected
        or not x_internal_secret
        or not secrets.compare_digest(x_internal_secret, expected)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=INVALID_INTERNAL_SECRET_ERROR_CODE,
        )
