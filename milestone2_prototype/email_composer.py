"""
Email composition module.

Builds well-formed MIME email messages ready to hand to an SMTP client.
Deliberately free of any network code so it's independently testable --
composing a message never touches a socket.
"""

from __future__ import annotations

import email.charset as _email_charset
from dataclasses import dataclass
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr, make_msgid
from pathlib import Path
from typing import List, Optional, Sequence

# By default, Python's email module base64-encodes UTF-8 text bodies.
# That's valid MIME but makes every message an unreadable blob -- annoying
# for logs, debugging, and anyone inspecting a raw .eml file. Quoted-printable
# keeps plain ASCII content readable as-is while still handling non-ASCII
# characters correctly.
_email_charset.add_charset("utf-8", _email_charset.QP, _email_charset.QP, "utf-8")


class EmailCompositionError(ValueError):
    """Raised when an email cannot be composed from the given inputs."""


@dataclass
class Attachment:
    filename: str
    content: bytes
    mime_subtype: str = "octet-stream"


@dataclass
class ComposedEmail:
    """A fully-built email, ready for an SMTP client to send."""

    sender: str
    recipients: List[str]
    cc: List[str]
    subject: str
    message: MIMEMultipart

    @property
    def all_recipients(self) -> List[str]:
        return [*self.recipients, *self.cc]

    def as_string(self) -> str:
        return self.message.as_string()


def compose_email(
    sender: str,
    recipients: Sequence[str],
    subject: str,
    body: str,
    *,
    sender_name: Optional[str] = None,
    cc: Optional[Sequence[str]] = None,
    is_html: bool = False,
    attachments: Optional[Sequence[Attachment]] = None,
) -> ComposedEmail:
    """Build a ComposedEmail from plain inputs.

    Raises EmailCompositionError on a missing subject/body or an empty
    recipient list, so bad input is caught before anything touches SMTP.
    """
    recipients = list(recipients or [])
    cc = list(cc or [])

    if not recipients:
        raise EmailCompositionError("At least one recipient is required")
    if not subject.strip():
        raise EmailCompositionError("Subject cannot be empty")
    if not body.strip():
        raise EmailCompositionError("Body cannot be empty")

    msg = MIMEMultipart("mixed")
    msg["From"] = formataddr((sender_name, sender)) if sender_name else sender
    msg["To"] = ", ".join(recipients)
    if cc:
        msg["Cc"] = ", ".join(cc)
    msg["Subject"] = subject
    msg["Message-ID"] = make_msgid()

    alt = MIMEMultipart("alternative")
    alt.attach(MIMEText(body, "html" if is_html else "plain", "utf-8"))
    msg.attach(alt)

    for att in attachments or []:
        part = MIMEApplication(att.content, _subtype=att.mime_subtype)
        part.add_header("Content-Disposition", "attachment", filename=att.filename)
        msg.attach(part)

    return ComposedEmail(sender=sender, recipients=recipients, cc=cc, subject=subject, message=msg)


def attachment_from_file(path: str) -> Attachment:
    """Convenience: build an Attachment by reading a file from disk."""
    p = Path(path)
    subtype = p.suffix.lstrip(".") or "octet-stream"
    return Attachment(filename=p.name, content=p.read_bytes(), mime_subtype=subtype)
