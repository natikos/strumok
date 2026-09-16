"""Secrets in Settings must not leak into logs/reprs.

`AuthSettings.secret_key` and `BrevoSettings.api_key` are `pydantic.SecretStr`
(#61) specifically so an accidental `print(settings)`, log line, or traceback
never exposes the JWT signing key or the Brevo API key.
"""

from app.core.config import settings


def test_auth_secret_key_is_masked_in_str_and_repr() -> None:
    secret_value = settings.auth.secret_key.get_secret_value()

    assert secret_value != ""
    assert secret_value not in str(settings.auth.secret_key)
    assert secret_value not in repr(settings.auth.secret_key)


def test_brevo_api_key_is_masked_in_str_and_repr() -> None:
    secret_value = settings.brevo.api_key.get_secret_value()

    assert secret_value not in str(settings.brevo.api_key)
    assert secret_value not in repr(settings.brevo.api_key)
