import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List, Optional

from app.config import settings

logger = logging.getLogger("automation.email")


class EmailSendError(Exception):
    """Raised when an email could not be delivered."""


def send_email(
    subject: str,
    body: str,
    recipients: List[str],
    is_html: bool = False,
    cc: Optional[List[str]] = None,
) -> None:
    """Send a single email via SMTP. Raises EmailSendError on failure."""
    if not recipients:
        raise EmailSendError("No recipients provided")
    if not settings.smtp_from_email:
        raise EmailSendError("SMTP_FROM_EMAIL is not configured (check your .env file)")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{settings.smtp_from_name} <{settings.smtp_from_email}>"
    msg["To"] = ", ".join(recipients)
    if cc:
        msg["Cc"] = ", ".join(cc)

    msg.attach(MIMEText(body, "html" if is_html else "plain"))

    all_recipients = list(recipients) + list(cc or [])

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30) as server:
            if settings.smtp_use_tls:
                server.starttls()
            if settings.smtp_user and settings.smtp_password:
                server.login(settings.smtp_user, settings.smtp_password)
            server.sendmail(settings.smtp_from_email, all_recipients, msg.as_string())
        logger.info("Email sent: %s -> %s", subject, all_recipients)
    except Exception as exc:  # noqa: BLE001 - surface any SMTP failure uniformly
        logger.exception("Failed to send email: %s", subject)
        raise EmailSendError(str(exc)) from exc
