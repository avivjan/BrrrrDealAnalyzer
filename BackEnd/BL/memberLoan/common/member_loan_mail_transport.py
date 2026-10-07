"""Sends Member Loan e-mail through the company's Gmail account (D8).

The same SMTP route as offer e-mails: `smtp.gmail.com:465` with the app
password in `EMAIL_PASSWORD`. Addresses and the password come from the
environment only. Tests replace `deliver_member_loan_email`.
"""

from __future__ import annotations

import logging
import os
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Sequence

logger = logging.getLogger(__name__)


class MemberLoanEmailNotSent(Exception):
    pass


@dataclass(frozen=True)
class MemberLoanEmailAttachment:
    filename: str
    content: bytes
    mime_type: str = "application"
    mime_subtype: str = "pdf"


def deliver_member_loan_email(
    *,
    sender_address: str,
    recipients: Sequence[str],
    subject: str,
    text_body: str,
    html_body: str,
    attachments: Sequence[MemberLoanEmailAttachment] = (),
) -> None:
    password = (os.getenv("EMAIL_PASSWORD") or "").strip()
    if not password:
        raise MemberLoanEmailNotSent("EMAIL_PASSWORD is not set")
    if not recipients:
        raise MemberLoanEmailNotSent("no recipient")
    message = EmailMessage()
    message["From"] = sender_address
    message["To"] = ", ".join(recipients)
    message["Subject"] = subject
    message.set_content(text_body)
    message.add_alternative(html_body, subtype="html")
    for attachment in attachments:
        message.add_attachment(
            attachment.content, maintype=attachment.mime_type, subtype=attachment.mime_subtype, filename=attachment.filename
        )
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as server:
            server.login(sender_address, password)
            server.send_message(message)
    except (smtplib.SMTPException, OSError) as error:
        # The server's own text can name the account; only the error type is kept.
        logger.error("member loan e-mail not sent: %s", type(error).__name__)
        raise MemberLoanEmailNotSent(type(error).__name__) from error
