"""
SMTP connection handling module.

Wraps smtplib with a small, reusable client: a context-managed connection,
TLS/auth handling, and retry-with-backoff on transient failures. Callers
never touch smtplib directly.
"""

from __future__ import annotations

import logging
import smtplib
import ssl
import time
from dataclasses import dataclass
from typing import Optional

from email_composer import ComposedEmail

logger = logging.getLogger("automation.smtp_client")


class SMTPSendError(Exception):
    """Raised after all retry attempts to send a message have failed."""


@dataclass
class SMTPConfig:
    host: str
    port: int = 587
    username: Optional[str] = None
    password: Optional[str] = None
    use_tls: bool = True
    timeout: int = 30
    max_retries: int = 3
    retry_backoff_seconds: float = 2.0


class SMTPClient:
    """A small, reusable SMTP client.

    Usage:
        with SMTPClient(config) as client:
            client.send(composed_email)
    """

    def __init__(self, config: SMTPConfig):
        self._config = config
        self._connection: Optional[smtplib.SMTP] = None

    def __enter__(self) -> "SMTPClient":
        self.connect()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def connect(self) -> None:
        cfg = self._config
        self._connection = smtplib.SMTP(cfg.host, cfg.port, timeout=cfg.timeout)
        self._connection.ehlo()
        if cfg.use_tls:
            context = ssl.create_default_context()
            self._connection.starttls(context=context)
            self._connection.ehlo()
        if cfg.username and cfg.password:
            self._connection.login(cfg.username, cfg.password)
        logger.info("Connected to SMTP server %s:%s", cfg.host, cfg.port)

    def close(self) -> None:
        if self._connection is not None:
            try:
                self._connection.quit()
            except Exception:  # noqa: BLE001 - connection may already be dead
                self._connection.close()
            finally:
                self._connection = None

    def send(self, email: ComposedEmail) -> None:
        """Send one composed email, retrying transient failures."""
        if self._connection is None:
            raise SMTPSendError("Not connected -- use `with SMTPClient(...) as client:`")

        last_error: Optional[Exception] = None
        for attempt in range(1, self._config.max_retries + 1):
            try:
                self._connection.sendmail(email.sender, email.all_recipients, email.as_string())
                logger.info("Sent '%s' to %s (attempt %d)", email.subject, email.all_recipients, attempt)
                return
            except (smtplib.SMTPServerDisconnected, smtplib.SMTPConnectError, ConnectionError) as exc:
                last_error = exc
                logger.warning("Transient SMTP error on attempt %d: %s", attempt, exc)
                if attempt < self._config.max_retries:
                    time.sleep(self._config.retry_backoff_seconds * attempt)
                    self._reconnect()
            except smtplib.SMTPException as exc:
                last_error = exc
                break  # not transient - retrying won't help

        raise SMTPSendError(f"Failed to send '{email.subject}' after retries: {last_error}") from last_error

    def _reconnect(self) -> None:
        self.close()
        self.connect()
