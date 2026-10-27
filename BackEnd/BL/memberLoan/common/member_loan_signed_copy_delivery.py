"""Delivering a fully signed copy (Amendment No. 1, Section 1.4).

Once every required member has signed, the signed copy is:
  - e-mailed, with the PDF attached, to the Lender, Yarden and the company
    (MEMBER_LOAN_LENDER_EMAIL, MEMBER_LOAN_YARDEN_EMAIL, MEMBER_LOAN_COMPANY_EMAIL),
    subject exactly "whales loan update" for a change or "whales loan statement"
    for a statement;
  - saved to the company's Google Drive folder "loan agreements".

Each attempt is one append-only delivery row; the newest row per channel is
the current state. A failure never undoes a signature. The scheduler retries a
failed channel until it has been tried AUTOMATIC_DELIVERY_ATTEMPTS times.
"""

from __future__ import annotations

import html
import logging
import re
import uuid
from datetime import timedelta
from typing import Optional
from uuid import UUID

from BL.memberLoan.common import member_loan_google_drive, member_loan_mail_transport, member_loan_settings
from BL.memberLoan.common.member_loan_access import MemberLoanMembers, load_member_loan_members
from BL.memberLoan.common.member_loan_ledger_service import append_member_loan_audit_entry
from BL.memberLoan.common.member_loan_settings import LOAN_TIME_ZONE, MemberLoanSettings, load_member_loan_settings
from BL.memberLoan.common.member_loan_signing_documents import DOCUMENT_KIND_MONTHLY_STATEMENT, SIGNATURE_MEANING_OBJECTED
from BL.memberLoan.common.member_loan_statement_document import format_long_date
from DAL.crud import member_loan as member_loan_crud
from DAL.data_models.memberLoan.models import MemberLoanSignedCopy, MemberLoanSignedCopyDelivery, MemberLoanSigningDocument
from db import SessionLocal

logger = logging.getLogger(__name__)

DELIVERY_CHANNEL_EMAIL = "email"
DELIVERY_CHANNEL_GOOGLE_DRIVE = "google_drive"
DELIVERY_CHANNELS = (DELIVERY_CHANNEL_EMAIL, DELIVERY_CHANNEL_GOOGLE_DRIVE)
DELIVERY_STATUS_SENT = "sent"
DELIVERY_STATUS_FAILED = "failed"
AUTOMATIC_DELIVERY_ATTEMPTS = 4  # the first attempt and three retries
FIRST_DELIVERY_GRACE_MINUTES = 10
SIGNED_CHANGE_EMAIL_SUBJECT = "whales loan update"
SIGNED_STATEMENT_EMAIL_SUBJECT = "whales loan statement"
CHARACTERS_NOT_ALLOWED_IN_FILE_NAMES = re.compile(r"[\\/:*?\"<>|\x00-\x1f]")


def signed_copy_email_subject(document: MemberLoanSigningDocument) -> str:
    return SIGNED_STATEMENT_EMAIL_SUBJECT if document.document_kind == DOCUMENT_KIND_MONTHLY_STATEMENT else SIGNED_CHANGE_EMAIL_SUBJECT


def signed_copy_file_name(document: MemberLoanSigningDocument, signed_copy: MemberLoanSignedCopy) -> str:
    completed_on = signed_copy.completed_at.astimezone(LOAN_TIME_ZONE).date().isoformat()
    content = document.document_content
    if document.document_kind == DOCUMENT_KIND_MONTHLY_STATEMENT:
        name = f"{completed_on} whales loan statement – {content['month_label']} – signed.pdf"
    else:
        change = content["change_rows"][0][1]
        amount = next((value for label, value in content["change_rows"] if label == "Amount"), None)
        name = f"{completed_on} whales loan update #{content['record_number']} – {change}{' ' + amount if amount else ''} – signed.pdf"
    return CHARACTERS_NOT_ALLOWED_IN_FILE_NAMES.sub("-", name)


def signed_copy_recipients(settings: MemberLoanSettings, members: MemberLoanMembers) -> list[str]:
    addresses = {
        "MEMBER_LOAN_LENDER_EMAIL": members.lender.email,
        "MEMBER_LOAN_YARDEN_EMAIL": members.yarden.email,
        "MEMBER_LOAN_COMPANY_EMAIL": settings.company_email,
    }
    missing = [name for name, address in addresses.items() if not address]
    if missing:
        raise member_loan_mail_transport.MemberLoanEmailNotSent(f"not set: {', '.join(missing)}")
    return list(dict.fromkeys(addresses.values()))


def compose_signed_copy_email(
    document: MemberLoanSigningDocument, signed_copy: MemberLoanSignedCopy, signatures, settings: MemberLoanSettings
) -> tuple[str, str, str]:
    content = document.document_content
    link = f"{settings.app_origin}/member-loan/sign/{document.id}"
    completed_on = format_long_date(signed_copy.completed_at.astimezone(LOAN_TIME_ZONE).date())
    lines = [content["title"], "", f"Every required signature was given. Completed on {completed_on}.", ""]
    for signature in signatures:
        verb = "Objected" if signature.signature_meaning == SIGNATURE_MEANING_OBJECTED else "Signed"
        when = format_long_date(signature.signed_at.astimezone(LOAN_TIME_ZONE).date())
        detail = f" Reason: {signature.objection_reason}" if signature.objection_reason else ""
        lines.append(f"- {verb} by {signature.typed_full_legal_name} on {when}.{detail}")
    lines += [
        "",
        "The signed copy is attached. It is also saved in the company's Google Drive folder \"loan agreements\".",
        f"SHA-256 of the signed copy: {signed_copy.signed_pdf_sha256}",
        "",
        f"Open it in the app: {link}",
    ]
    esc = html.escape
    html_body = (
        "<html><body style='font-family:Helvetica,Arial,sans-serif;color:#1f2933;line-height:1.5'>"
        f"<h2 style='color:#0b1f3a'>{esc(content['title'])}</h2>"
        f"<p>Every required signature was given. Completed on {esc(completed_on)}.</p><ul>"
        + "".join(
            f"<li>{esc('Objected' if s.signature_meaning == SIGNATURE_MEANING_OBJECTED else 'Signed')} by "
            f"{esc(s.typed_full_legal_name)} on {esc(format_long_date(s.signed_at.astimezone(LOAN_TIME_ZONE).date()))}"
            f"{esc(' Reason: ' + s.objection_reason) if s.objection_reason else ''}</li>"
            for s in signatures
        )
        + "</ul><p>The signed copy is attached. It is also saved in the company's Google Drive folder "
        "&quot;loan agreements&quot;.</p>"
        f"<p style='color:#6b7280;font-size:12px'>SHA-256 of the signed copy: {esc(signed_copy.signed_pdf_sha256)}</p>"
        f"<p><a href='{esc(link, quote=True)}'>Open it in the app</a></p></body></html>"
    )
    return signed_copy_email_subject(document), "\n".join(lines) + "\n", html_body


def _attempt(channel: str, signed_copy: MemberLoanSignedCopy, document: MemberLoanSigningDocument, signatures,
             settings: MemberLoanSettings, members: MemberLoanMembers) -> Optional[str]:
    """Deliver on one channel. Returns the Drive file id (or None); raises on failure."""

    file_name = signed_copy_file_name(document, signed_copy)
    if channel == DELIVERY_CHANNEL_EMAIL:
        subject, text_body, html_body = compose_signed_copy_email(document, signed_copy, signatures, settings)
        member_loan_mail_transport.deliver_member_loan_email(
            sender_address=settings.sender_address,
            recipients=signed_copy_recipients(settings, members),
            subject=subject,
            text_body=text_body,
            html_body=html_body,
            attachments=[member_loan_mail_transport.MemberLoanEmailAttachment(file_name, bytes(signed_copy.signed_pdf))],
        )
        return None
    return member_loan_google_drive.save_pdf_to_loan_agreements_folder(file_name, bytes(signed_copy.signed_pdf))


def _record_delivery(signed_copy: MemberLoanSignedCopy, document: MemberLoanSigningDocument, channel: str,
                     status: str, external_file_id: Optional[str], error_text: Optional[str]) -> None:
    with SessionLocal() as db:
        member_loan_crud.acquire_member_loan_write_lock(db)
        member_loan_crud.add_member_loan_row(db, MemberLoanSignedCopyDelivery(
            id=uuid.uuid4(), signed_copy_id=signed_copy.id, delivery_channel=channel, delivery_status=status,
            external_file_id=external_file_id, error_text=error_text, attempted_at=member_loan_settings.utc_now(),
        ))
        action = {
            (DELIVERY_CHANNEL_EMAIL, DELIVERY_STATUS_SENT): "signed_copy_emailed",
            (DELIVERY_CHANNEL_EMAIL, DELIVERY_STATUS_FAILED): "signed_copy_email_failed",
            (DELIVERY_CHANNEL_GOOGLE_DRIVE, DELIVERY_STATUS_SENT): "signed_copy_saved_to_drive",
            (DELIVERY_CHANNEL_GOOGLE_DRIVE, DELIVERY_STATUS_FAILED): "signed_copy_drive_save_failed",
        }[(channel, status)]
        append_member_loan_audit_entry(
            db, actor_user_id=None, actor_username="system", action=action, event_id=document.event_id,
            detail={"document_id": str(document.id), "signed_copy_id": str(signed_copy.id), "drive_file_id": external_file_id,
                    "error": error_text},
        )
        db.commit()


def channels_still_to_deliver(deliveries: list[MemberLoanSignedCopyDelivery], *, respect_attempt_limit: bool) -> list[str]:
    pending = []
    for channel in DELIVERY_CHANNELS:
        attempts = [d for d in deliveries if d.delivery_channel == channel]
        if any(d.delivery_status == DELIVERY_STATUS_SENT for d in attempts):
            continue
        if respect_attempt_limit and len(attempts) >= AUTOMATIC_DELIVERY_ATTEMPTS:
            continue
        pending.append(channel)
    return pending


def deliver_signed_copy(signed_copy_id: UUID, *, respect_attempt_limit: bool = True) -> dict[str, str]:
    """Try every channel not delivered yet. Never raises. Returns channel -> sent | failed."""

    outcomes: dict[str, str] = {}
    try:
        with SessionLocal() as db:
            settings = load_member_loan_settings()
            members = load_member_loan_members(db, settings)
            signed_copy = member_loan_crud.get_member_loan_signed_copy(db, signed_copy_id)
            document = member_loan_crud.get_member_loan_signing_document(db, signed_copy.document_id)
            signatures = member_loan_crud.list_member_loan_signatures(db, document.id)
            deliveries = member_loan_crud.list_member_loan_signed_copy_deliveries(db, signed_copy.id)
            db.expunge_all()
    except Exception:  # noqa: BLE001 -- a delivery problem must never break what triggered it
        logger.exception("member loan: could not load signed copy %s for delivery", signed_copy_id)
        return outcomes
    for channel in channels_still_to_deliver(deliveries, respect_attempt_limit=respect_attempt_limit):
        try:
            external_file_id = _attempt(channel, signed_copy, document, signatures, settings, members)
            status, error_text = DELIVERY_STATUS_SENT, None
        except Exception as error:  # noqa: BLE001 -- recorded as a failed delivery and retried later
            status, external_file_id, error_text = DELIVERY_STATUS_FAILED, None, (str(error) or type(error).__name__)[:500]
            logger.warning("member loan signed copy %s: %s delivery failed: %s", signed_copy_id, channel, type(error).__name__)
        outcomes[channel] = status
        try:
            _record_delivery(signed_copy, document, channel, status, external_file_id, error_text)
        except Exception:  # noqa: BLE001
            logger.exception("member loan: could not record the %s delivery of %s", channel, signed_copy_id)
    return outcomes


def deliver_signed_copy_after_commit(signed_copy_id: UUID) -> None:
    """FastAPI background task."""
    deliver_signed_copy(signed_copy_id)


def retry_failed_signed_copy_deliveries() -> int:
    """For the scheduler: retry every signed copy with a channel still to deliver. Returns how many were tried.

    A copy completed in the last few minutes is left to its own after-commit
    delivery, so the two never send the same e-mail twice."""

    settled_before = member_loan_settings.utc_now() - timedelta(minutes=FIRST_DELIVERY_GRACE_MINUTES)
    with SessionLocal() as db:
        signed_copies = member_loan_crud.list_member_loan_signed_copies(db)
        to_retry = [
            c.id for c in signed_copies
            if c.completed_at <= settled_before
            and channels_still_to_deliver(member_loan_crud.list_member_loan_signed_copy_deliveries(db, c.id), respect_attempt_limit=True)
        ]
    for signed_copy_id in to_retry:
        deliver_signed_copy(signed_copy_id)
    return len(to_retry)
