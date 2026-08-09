"""Test that verification email is sent on signup."""

from unittest.mock import patch, MagicMock
from starlette.testclient import TestClient

from app.core.email import EmailSendError


class TestRegisterEmailVerification:
    """Email verification should be sent automatically on user registration."""

    @patch("app.api.auth.service.send_email")
    def test_register_sends_verification_email(
        self, mock_send_email: MagicMock, client: TestClient
    ) -> None:
        """Verify email is sent automatically on user registration."""
        payload = {
            "email": "newuser@example.com",
            "first_name": "John",
            "last_name": "Doe",
            "password": "SecurePassword123!",
        }

        response = client.post("/auth/register", json=payload)

        assert response.status_code == 201
        assert response.json()["email"] == "newuser@example.com"

        # Verify send_email was called with proper parameters
        assert mock_send_email.call_count == 1
        call_kwargs = mock_send_email.call_args[1]
        assert call_kwargs["to_email"] == "newuser@example.com"
        assert call_kwargs["to_name"] == "John"
        assert call_kwargs["subject"] == "Verify your Strumok email"
        assert "verify-email" in call_kwargs["html_content"]
        assert "Verify email" in call_kwargs["html_content"]

    @patch("app.api.auth.service.send_email")
    def test_register_fails_if_email_send_fails(
        self, mock_send_email: MagicMock, client: TestClient
    ) -> None:
        """Registration fails if verification email cannot be sent."""
        mock_send_email.side_effect = EmailSendError("Brevo is not configured")

        payload = {
            "email": "failuser@example.com",
            "first_name": "Jane",
            "last_name": "Smith",
            "password": "SecurePassword123!",
        }

        response = client.post("/auth/register", json=payload)

        assert response.status_code == 502
        assert response.json()["detail"] == "verificationEmailSendFailed"
