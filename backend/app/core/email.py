import httpx

from app.core.config import settings

BREVO_SEND_URL = "https://api.brevo.com/v3/smtp/email"


class EmailSendError(Exception):
    pass


def send_email(*, to_email: str, to_name: str, subject: str, html_content: str) -> None:
    if not settings.brevo.api_key or not settings.brevo.sender_email:
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
                "api-key": settings.brevo.api_key,
                "content-type": "application/json",
            },
            timeout=10.0,
        )
    except httpx.HTTPError as exc:
        raise EmailSendError("Brevo request failed") from exc

    if response.status_code >= 400:
        raise EmailSendError(f"Brevo responded with status {response.status_code}")
