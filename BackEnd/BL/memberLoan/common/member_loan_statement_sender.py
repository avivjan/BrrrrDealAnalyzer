"""The monthly statement e-mail (run by `manage.py send-member-loan-statement`, a Render Cron Job).

Never sends the same month twice:
  1. a `sending` row is committed first; a partial unique index allows only one
     live real send (`sending` or `sent`) per month, so two runs cannot both pass;
  2. only then is the e-mail sent, and the row moves to `sent` or `failed`.
A crash between 1 and 2 leaves `sending`: the month is never re-sent
automatically (a missed e-mail can be sent by hand; a double one cannot be
taken back). A `failed` month needs `--retry-failed`.

Dry run (the default until MEMBER_LOAN_EMAIL_DRY_RUN=false): renders the
e-mail and the PDF into files, logs the dry run, sends nothing, locks nothing.

A real send locks the month (R2): proposals still pending for it expire and
both members are told.
"""

from __future__ import annotations

import hashlib
import html
import os
import uuid
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DbSession

from BL.memberLoan.common import member_loan_mail_transport, member_loan_settings
from BL.memberLoan.common.member_loan_access import load_member_loan_members
from BL.memberLoan.common.member_loan_engine import MEMBER_LOAN_ENGINE_VERSION, first_day_of_next_month, first_day_of_previous_month
from BL.memberLoan.common.member_loan_ledger_service import (
    append_member_loan_audit_entry,
    expire_stale_proposals_in_own_transaction,
    load_member_loan_ledger_snapshot,
    member_loan_terms,
)
from BL.memberLoan.common.member_loan_notifications import send_member_loan_notification_after_commit
from BL.memberLoan.common.member_loan_statement_document import format_long_date, format_month_label
from BL.memberLoan.common.member_loan_statement_pdf import render_member_loan_statement_pdf
from BL.memberLoan.common.member_loan_statement_service import build_member_loan_statement_for_month, count_proposals_waiting_for_month
from DAL.crud import member_loan as member_loan_crud
from DAL.data_models.memberLoan.models import MemberLoanStatementSend

OBJECTION_PERIOD_DAYS = 30
SEND_STATUS_SENDING = "sending"
SEND_STATUS_SENT = "sent"
SEND_STATUS_FAILED = "failed"
SEND_STATUS_DRY_RUN = "dry_run"


@dataclass
class MemberLoanStatementSendResult:
    statement_month: date
    outcome: str  # sent | dry_run | skipped | failed | refused
    message: str
    written_files: list[str] = field(default_factory=list)


def _statement_email(document: dict, app_origin: str, sent_on: date, objection_deadline: date) -> tuple[str, str, str]:
    month_label = format_month_label(date.fromisoformat(document["statement_date"]) - timedelta(days=1))
    amount_owed = document["summary_rows"][-1][1]
    subject = f"Member Loan statement – {month_label}: Amount Owed {amount_owed}"
    link = f"{app_origin}/member-loan?tab=statements&month={document['statement_month']}"
    text_lines = [document["title"], ""]
    text_lines += [f"{label}: {value}" for label, value in document["summary_rows"]]
    text_lines += ["", "What happened this month:"] + [f"- {s}" for s in document["what_happened_sentences"]]
    if document["warnings"]:
        text_lines += [""] + document["warnings"]
    text_lines += [
        "",
        "The attached PDF shows how every figure was calculated.",
        f"Sent on {format_long_date(sent_on)}. Objections must be made in writing by {format_long_date(objection_deadline)}.",
        "",
        document["binding_sentence"],
        "",
        f"Open it in the app: {link}",
    ]
    esc = html.escape
    rows = "".join(
        f"<tr><td style='padding:4px 16px 4px 0'>{esc(label)}</td><td style='padding:4px 0;text-align:right'><strong>{esc(value)}</strong></td></tr>"
        for label, value in document["summary_rows"]
    )
    html_body = (
        "<html><body style='font-family:Helvetica,Arial,sans-serif;color:#1f2933;line-height:1.5'>"
        f"<h2 style='color:#0b1f3a'>{esc(document['title'])}</h2>"
        f"<table style='border-collapse:collapse'>{rows}</table>"
        "<p><strong>What happened this month</strong></p><ul>"
        + "".join(f"<li>{esc(s)}</li>" for s in document["what_happened_sentences"])
        + "</ul>"
        + "".join(f"<p style='color:#9a3412'><strong>{esc(w)}</strong></p>" for w in document["warnings"])
        + "<p>The attached PDF shows how every figure was calculated.</p>"
        f"<p>Sent on {esc(format_long_date(sent_on))}. Objections must be made in writing by {esc(format_long_date(objection_deadline))}.</p>"
        f"<p><strong>{esc(document['binding_sentence'])}</strong></p>"
        f"<p><a href='{esc(link, quote=True)}'>Open the statement in the app</a></p>"
        "</body></html>"
    )
    return subject, "\n".join(text_lines) + "\n", html_body


def _notify_expired(expired) -> None:
    for outcome in expired:
        send_member_loan_notification_after_commit(outcome.decision, outcome.event_id)


def send_member_loan_statement(
    db: DbSession,
    *,
    statement_month: Optional[date] = None,
    dry_run_requested: bool = False,
    retry_failed: bool = False,
    dry_run_output_directory: Optional[Path] = None,
) -> MemberLoanStatementSendResult:
    settings = member_loan_settings.load_member_loan_settings()
    members = load_member_loan_members(db, settings)
    today = member_loan_settings.new_york_today()
    month = statement_month or first_day_of_previous_month(today)
    dry_run = dry_run_requested or settings.statement_email_dry_run

    terms = member_loan_terms()
    if month.day != 1 or month < terms.loan_effective_date:
        return MemberLoanStatementSendResult(month, "refused", "There is no statement for that month.")
    if first_day_of_next_month(month) > today:
        return MemberLoanStatementSendResult(month, "refused", f"{format_month_label(month)} is not over yet in New York.")
    recipients = [m.email for m in (members.lender, members.yarden)]
    if not all(recipients):
        return MemberLoanStatementSendResult(month, "refused", "Both MEMBER_LOAN_LENDER_EMAIL and MEMBER_LOAN_YARDEN_EMAIL must be set.")

    _notify_expired(expire_stale_proposals_in_own_transaction(db))

    if not dry_run:
        earlier_real_sends = [s for s in member_loan_crud.list_member_loan_statement_sends(db, month) if not s.is_dry_run]
        if any(s.status == SEND_STATUS_SENT for s in earlier_real_sends):
            return MemberLoanStatementSendResult(month, "skipped", f"The statement for {format_month_label(month)} was already sent.")
        if any(s.status == SEND_STATUS_SENDING for s in earlier_real_sends):
            return MemberLoanStatementSendResult(
                month, "skipped", "An earlier send was interrupted. Check the members' inboxes by hand before doing anything else."
            )
        if any(s.status == SEND_STATUS_FAILED for s in earlier_real_sends) and not retry_failed:
            return MemberLoanStatementSendResult(month, "skipped", "An earlier send failed. Run again with --retry-failed to try once more.")

    snapshot = load_member_loan_ledger_snapshot(db)
    document = build_member_loan_statement_for_month(snapshot, members, month).as_plain_dict()
    objection_deadline = today + timedelta(days=OBJECTION_PERIOD_DAYS)
    sent_line = (
        f"Sent on {format_long_date(today)} to {', '.join(recipients)}. "
        f"Objections must be made in writing by {format_long_date(objection_deadline)}."
    )
    pdf_bytes = render_member_loan_statement_pdf(document, sent_line=sent_line)
    pdf_sha256 = hashlib.sha256(pdf_bytes).hexdigest()
    subject, text_body, html_body = _statement_email(document, settings.app_origin, today, objection_deadline)
    pdf_filename = f"member-loan-statement-{document['statement_month']}.pdf"

    send_row = MemberLoanStatementSend(
        id=uuid.uuid4(),
        statement_month=month,
        is_dry_run=dry_run,
        status=SEND_STATUS_DRY_RUN if dry_run else SEND_STATUS_SENDING,
        recipients=recipients,
        sender_address=settings.sender_address,
        statement_snapshot=document,
        engine_version=MEMBER_LOAN_ENGINE_VERSION,
        pdf_sha256=pdf_sha256,
        proposals_left_out_count=count_proposals_waiting_for_month(snapshot, month),
        started_at=member_loan_settings.utc_now(),
    )

    if dry_run:
        output_directory = dry_run_output_directory or Path(os.getenv("MEMBER_LOAN_DRY_RUN_DIRECTORY") or "member-loan-dry-runs")
        output_directory.mkdir(parents=True, exist_ok=True)
        written = []
        for suffix, content in ((".pdf", pdf_bytes), (".txt", f"Subject: {subject}\n\n{text_body}".encode()), (".html", html_body.encode())):
            path = output_directory / f"member-loan-statement-{document['statement_month']}{suffix}"
            path.write_bytes(content)
            written.append(str(path))
        member_loan_crud.acquire_member_loan_write_lock(db)
        member_loan_crud.add_member_loan_row(db, send_row)
        append_member_loan_audit_entry(
            db, actor_user_id=None, actor_username="system", action="statement_dry_run",
            detail={"statement_month": document["statement_month"], "pdf_sha256": pdf_sha256, "recipients": recipients},
        )
        db.commit()
        return MemberLoanStatementSendResult(month, "dry_run", "Rendered only; nothing was sent.", written)

    member_loan_crud.acquire_member_loan_write_lock(db)
    try:
        member_loan_crud.add_member_loan_row(db, send_row)
        db.commit()
    except IntegrityError:
        db.rollback()
        return MemberLoanStatementSendResult(month, "skipped", "Another run is sending this month's statement.")

    try:
        member_loan_mail_transport.deliver_member_loan_email(
            sender_address=settings.sender_address,
            recipients=recipients,
            subject=subject,
            text_body=text_body,
            html_body=html_body,
            attachments=[member_loan_mail_transport.MemberLoanEmailAttachment(pdf_filename, pdf_bytes)],
        )
    except Exception as error:  # noqa: BLE001 -- recorded below; the month stays unsent
        member_loan_crud.acquire_member_loan_write_lock(db)
        send_row.status = SEND_STATUS_FAILED
        send_row.error_text = (str(error) or type(error).__name__)[:500]
        append_member_loan_audit_entry(
            db, actor_user_id=None, actor_username="system", action="statement_send_failed",
            detail={"statement_month": document["statement_month"], "error": send_row.error_text},
        )
        db.commit()
        return MemberLoanStatementSendResult(month, "failed", f"The e-mail was not sent: {send_row.error_text}")

    member_loan_crud.acquire_member_loan_write_lock(db)
    send_row.status = SEND_STATUS_SENT
    send_row.sent_at = member_loan_settings.utc_now()
    send_row.objection_deadline = objection_deadline
    append_member_loan_audit_entry(
        db, actor_user_id=None, actor_username="system", action="statement_sent",
        detail={"statement_month": document["statement_month"], "pdf_sha256": pdf_sha256, "recipients": recipients,
                "objection_deadline": objection_deadline.isoformat(), "engine_version": MEMBER_LOAN_ENGINE_VERSION},
    )
    db.commit()
    _notify_expired(expire_stale_proposals_in_own_transaction(db))
    return MemberLoanStatementSendResult(month, "sent", f"Sent the statement for {format_month_label(month)} to {', '.join(recipients)}.")
