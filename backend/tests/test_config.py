"""Secrets in Settings must not leak into logs/reprs.

`AuthSettings.secret_key` and `BrevoSettings.api_key` are `pydantic.SecretStr`
(#61) specifically so an accidental `print(settings)`, log line, or traceback
never exposes the JWT signing key or the Brevo API key. SecretStr's masking
behavior is pydantic's guarantee, not ours to re-test — what we assert here is
that these two fields are actually typed as SecretStr.
"""

from pydantic import SecretStr

from app.core.config import AuthSettings, BrevoSettings


def test_auth_secret_key_is_a_secret_str() -> None:
    assert AuthSettings.model_fields["secret_key"].annotation is SecretStr


def test_brevo_api_key_is_a_secret_str() -> None:
    assert BrevoSettings.model_fields["api_key"].annotation is SecretStr
