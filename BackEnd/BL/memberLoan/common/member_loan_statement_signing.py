"""Asking both members to sign each sent statement (Amendment No. 1, Section 6.2).

The statement e-mail on the 1st is the first request: it attaches the statement
with its acknowledgment page and links to the signing page. Then, from 09:00 in
New York each day, each member who has not yet signed or objected gets one
reminder, "whales loan statement – please sign", until both have acted or the
30 days to object have passed (the owner's choice; Section 8.3 makes the
statement binding then anyway).

A reminder row is claimed (unique per month, member and day) before the e-mail
goes out, so a day never gets two; a failed send is kept in the audit trail.
"""

from __future__ import annotations

import html
import logging
import uuid
from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional
from uuid import UUID

from sqlalchemy.exc import IntegrityError

from BL.memberLoan.common import member_loan_mail_transport, member_loan_settings
from BL.memberLoan.common.member_loan_access import MemberLoanMember, load_member_loan_members
from BL.memberLoan.common.member_loan_ledger_service import append_member_loan_audit_entry
from BL.memberLoan.common.member_loan_settings import LOAN_TIME_ZONE, MemberLoanMisconfigured, MemberLoanSettings, load_member_loan_settings
from BL.memberLoan.common.member_loan_signing_documents import DOCUMENT_KIND_MONTHLY_STATEMENT
from BL.memberLoan.common.member_loan_signing_service import (
    create_statement_signing_document,
    signature_state_of,
    statement_response_deadline,
)
from BL.memberLoan.common.member_loan_statement_document import format_long_date, format_month_label
from DAL.crud import member_loan as member_loan_crud
from DAL.data_models.memberLoan.models import MemberLoanStatementSignatureReminder
from db import SessionLocal

logger = logging.getLogger(__name__)

PLEASE_SIGN_STATEMENT_EMAIL_SUBJECT = "whales loan statement – please sign"
EARLIEST_REMINDER_HOUR_IN_NEW_YORK = 9


def statement_signing_link(settings: MemberLoanSettings, document_id) -> str:
    return f"{settings.app_origin}/member-loan/sign/{document_id}"


@dataclass(frozen=True)
class StatementAwaitingSignature:
    """What a reminder needs, read before the session closes."""

    document_id: UUID
    statement_month: date
    content: dict
    response_deadline: Optional[date]


def compose_statement_signature_reminder(
    statement: StatementAwaitingSignature, member: MemberLoanMember, settings: MemberLoanSettings
) -> tuple[str, str, str]:
    content = statement.content
    deadline = statement.response_deadline
    link = statement_signing_link(settings, statement.document_id)
    lines = [
        f"Please sign the Member Loan statement for {content['month_label']}, or object to it with your reason.",
        f"Amount Owed on {format_long_date(date.fromisoformat(content['statement_date']))}: {content['amount_owed']}.",
    ]
    if deadline is not None:
        lines.append(f"You can sign or object until {format_long_date(deadline)}. After that the statement is binding (Section 8.3).")
    lines += ["", f"Open {link} and sign in with your passkey. This link does not sign anything by itself."]
    esc = html.escape
    html_body = (
        "<html><body style='font-family:Helvetica,Arial,sans-serif;color:#1f2933;line-height:1.5'>"
        + "".join(f"<p>{esc(line)}</p>" for line in lines[:-2])
        + f"<p><a href='{esc(link, quote=True)}'>Open the statement in the app</a> and sign in with your passkey. "
        "This link does not sign anything by itself.</p></body></html>"
    )
    return PLEASE_SIGN_STATEMENT_EMAIL_SUBJECT, "\n".join(lines) + "\n", html_body


def claim_todays_statement_reminder(db, statement_month: date, username: str, today: date) -> bool:
    """Insert today's reminder row in its own savepoint. False when today's is already claimed."""

    try:
        with db.begin_nested():
            member_loan_crud.add_member_loan_row(db, MemberLoanStatementSignatureReminder(
                id=uuid.uuid4(), statement_month=statement_month, recipient_username=username, reminder_date=today,
                sent_at=member_loan_settings.utc_now(),
            ))
    except IntegrityError:
        return False
    return True


def _send_reminder(statement: StatementAwaitingSignature, member: MemberLoanMember, settings: MemberLoanSettings) -> None:
    subject, text_body, html_body = compose_statement_signature_reminder(statement, member, settings)
    try:
        if not member.email:
            raise member_loan_mail_transport.MemberLoanEmailNotSent(f"no e-mail address configured for {member.display_name}")
        member_loan_mail_transport.deliver_member_loan_email(
            sender_address=settings.sender_address, recipients=[member.email], subject=subject, text_body=text_body, html_body=html_body,
        )
        action, detail = "statement_signature_reminder_sent", {}
    except Exception as error:  # noqa: BLE001 -- recorded; tomorrow's reminder tries again
        action, detail = "statement_signature_reminder_failed", {"error": (str(error) or type(error).__name__)[:200]}
    with SessionLocal() as db:
        member_loan_crud.acquire_member_loan_write_lock(db)
        append_member_loan_audit_entry(
            db, actor_user_id=None, actor_username="system", action=action,
            detail={"statement_month": statement.statement_month.isoformat(), "recipient": member.username, **detail},
        )
        db.commit()


def send_due_statement_signature_reminders(now: Optional[datetime] = None) -> int:
    """For the scheduler. Returns how many reminders went out (or were tried)."""

    now_in_new_york = (now or member_loan_settings.utc_now()).astimezone(LOAN_TIME_ZONE)
    if now_in_new_york.hour < EARLIEST_REMINDER_HOUR_IN_NEW_YORK:
        return 0
    today = now_in_new_york.date()
    try:
        settings = load_member_loan_settings()
    except MemberLoanMisconfigured:
        return 0
    due: list[tuple[StatementAwaitingSignature, MemberLoanMember]] = []
    with SessionLocal() as db:
        members = load_member_loan_members(db, settings)
        for document in member_loan_crud.list_member_loan_signing_documents(db):
            if document.document_kind != DOCUMENT_KIND_MONTHLY_STATEMENT:
                continue
            deadline = statement_response_deadline(db, document)
            if deadline is None or today > deadline:
                continue
            state = signature_state_of(db, document)
            statement = StatementAwaitingSignature(document.id, document.statement_month, document.document_content, deadline)
            for member in (members.lender, members.yarden):
                if member.username in document.required_signer_usernames and not state.has_acted(member.username):
                    if claim_todays_statement_reminder(db, document.statement_month, member.username, today):
                        due.append((statement, member))
        db.commit()
    for statement, member in due:
        _send_reminder(statement, member, settings)
    return len(due)


def create_missing_statement_signing_documents() -> int:
    """A month sent before signing existed (or whose document could not be made) gets its document now,
    while its 30 days are still running. Returns how many were created."""

    try:
        settings = load_member_loan_settings()
    except MemberLoanMisconfigured:
        return 0
    created = 0
    today = member_loan_settings.new_york_today()
    with SessionLocal() as db:
        members = load_member_loan_members(db, settings)
        for send in member_loan_crud.list_member_loan_statement_sends(db):
            if send.is_dry_run or send.status != "sent" or send.sent_at is None:
                continue
            if member_loan_crud.get_member_loan_signing_document_for_statement_month(db, send.statement_month) is not None:
                continue
            if send.objection_deadline is not None and today > send.objection_deadline:
                continue
            sent_on = send.sent_at.astimezone(LOAN_TIME_ZONE).date()
            deadline_text = format_long_date(send.objection_deadline) if send.objection_deadline else "30 days after it was sent"
            sent_line = (
                f"Sent on {format_long_date(sent_on)} to {', '.join(send.recipients)}. "
                f"Objections must be made in writing by {deadline_text}."
            )
            member_loan_crud.acquire_member_loan_write_lock(db)
            create_statement_signing_document(db, statement_document=send.statement_snapshot, members=members, sent_line=sent_line)
            db.commit()
            created += 1
            logger.info("member loan: created the signing document for %s", format_month_label(send.statement_month))
    return created
