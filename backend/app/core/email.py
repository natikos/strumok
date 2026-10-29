import logging

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

BREVO_SEND_URL = "https://api.brevo.com/v3/smtp/email"


class EmailSendError(Exception):
    pass


# ENVIRONMENT=e2e only: sent emails land here instead of Brevo, and the e2e
# router reads them back (an invite link, a reset link).
e2e_outbox: list[dict[str, str]] = []


def send_email(*, to_email: str, to_name: str, subject: str, html_content: str) -> None:
    if settings.environment == "e2e":
        e2e_outbox.append(
            {"to": to_email, "subject": subject, "html_content": html_content}
        )
        return

    if not settings.brevo.api_key.get_secret_value() or not settings.brevo.sender_email:
        raise EmailSendError("Brevo is not configured")

    payload = {
        "sender": {
            "email": settings.brevo.sender_email,
            "name": settings.brevo.sender_name,
        },
        "to": [{"email": to_email, "name": to_name}],
        "subject": subject,
        "htmlContent": html_content,
    }

    try:
        response = httpx.post(
            BREVO_SEND_URL,
            json=payload,
            headers={
                "api-key": settings.brevo.api_key.get_secret_value(),
                "content-type": "application/json",
            },
            timeout=10.0,
        )
    except httpx.HTTPError as exc:
        logger.exception("Brevo request failed")
        raise EmailSendError("Brevo request failed") from exc

    if response.status_code >= 400:
        logger.error("Brevo responded with status %s", response.status_code)
        raise EmailSendError(f"Brevo responded with status {response.status_code}")
