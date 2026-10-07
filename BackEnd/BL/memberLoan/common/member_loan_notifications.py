"""E-mails about proposals and decisions (D5, D16), sent after the change commits.

Who gets what:
  proposed   -> the other member only, with a link to the approval card. The
                link carries no token: it opens the app, which asks for a passkey.
  approved, rejected, cancelled, expired -> both members.

`send_member_loan_notification_after_commit` is the FastAPI background task.
It never raises: the outcome (sent or failed) is appended to the Member Loan
audit trail, and a failure never undoes the change it describes.
"""

from __future__ import annotations

import html
import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional
from uuid import UUID

from BL.memberLoan.common import member_loan_mail_transport
from BL.memberLoan.common.member_loan_access import MemberLoanMember, MemberLoanMembers, load_member_loan_members
from BL.memberLoan.common.member_loan_engine import (
    REVERSAL,
    YARDEN_ADDITIONAL_WITHDRAWAL_INCREASE,
)
from BL.memberLoan.common.member_loan_ledger_service import (
    DECISION_APPROVED,
    DECISION_CANCELLED,
    DECISION_EXPIRED,
    DECISION_REJECTED,
    MemberLoanLedgerSnapshot,
    append_member_loan_audit_entry,
    load_member_loan_ledger_snapshot,
    plain_event_name,
    reversed_event_summary,
)
from BL.memberLoan.common.member_loan_settings import LOAN_TIME_ZONE, MemberLoanSettings, load_member_loan_settings
from BL.memberLoan.common.member_loan_statement_document import (
    BUCKET_PLAIN_LABELS,
    YARDEN_INCREASE_WARNING,
    format_long_date,
    format_money,
)
from DAL.crud import member_loan as member_loan_crud
from DAL.data_models.memberLoan.models import MemberLoanEvent
from db import SessionLocal

logger = logging.getLogger(__name__)

NOTIFICATION_PROPOSED = "proposed"
NOTIFICATION_KINDS = (NOTIFICATION_PROPOSED, DECISION_APPROVED, DECISION_REJECTED, DECISION_CANCELLED, DECISION_EXPIRED)
BUCKETS_SHOWN_IN_EMAILS = ("original_principal", "capitalized_interest", "total_balance", "accrued_interest", "interest_payable", "amount_owed")


@dataclass(frozen=True)
class MemberLoanNotificationMessage:
    recipients: tuple[str, ...]
    subject: str
    text_body: str
    html_body: str


def _bucket_rows(before: dict, after: dict, lender_name: str) -> list[tuple[str, str, str]]:
    rows = []
    for key in BUCKETS_SHOWN_IN_EMAILS:
        if key == "interest_payable" and before.get(key) == "0.00" and after.get(key) == "0.00":
            continue
        label = BUCKET_PLAIN_LABELS[key].format(lender=lender_name)
        rows.append((label, format_money(Decimal(before[key])), format_money(Decimal(after[key]))))
    return rows


def _event_detail_lines(snapshot: MemberLoanLedgerSnapshot, event: MemberLoanEvent, members: MemberLoanMembers) -> list[str]:
    lines = [f"Change: {plain_event_name(event.event_type, members)}"]
    if event.event_type == REVERSAL:
        summary = reversed_event_summary(snapshot, event, members)
        lines.append(f"It reverses: {summary or 'an earlier change'}")
        if event.reversal_reason:
            lines.append(f"Reason: {event.reversal_reason}")
    lines.append(f"Date it takes effect: {format_long_date(event.effective_date)}")
    if event.amount is not None:
        lines.append(f"Amount: {format_money(Decimal(event.amount))}")
    if event.interest_election_choice:
        choice = "paid in cash" if event.interest_election_choice == "cash" else "added to the debt (reinvested)"
        lines.append(f"Interest for the month before {format_long_date(event.effective_date)}: {choice}")
    if event.written_agreement_date and event.written_agreement_description:
        lines.append(f"Written agreement: {event.written_agreement_date.isoformat()} - \"{event.written_agreement_description}\"")
    if event.payment_reference:
        lines.append(f"Payment reference: {event.payment_reference}")
    if event.note:
        lines.append(f"Note: {event.note}")
    proposed_on = event.proposed_at.astimezone(LOAN_TIME_ZONE).date()
    lines.append(f"Proposed by {members.display_name_for(event.proposed_by_username)} on {format_long_date(proposed_on)}.")
    decision = snapshot.decisions_by_event_id.get(event.id)
    if decision is not None:
        decided_on = format_long_date(decision.decided_at.astimezone(LOAN_TIME_ZONE).date())
        who = "the system" if decision.decided_by_user_id is None else members.display_name_for(decision.decided_by_username)
        lines.append(f"{decision.decision.capitalize()} by {who} on {decided_on}.")
        if decision.decision_reason and event.event_type != REVERSAL:
            lines.append(f"Reason: {decision.decision_reason}")
        elif decision.decision_reason and decision.decision != DECISION_APPROVED:
            lines.append(f"Reason for the decision: {decision.decision_reason}")
    return lines


def compose_member_loan_notification(
    kind: str,
    snapshot: MemberLoanLedgerSnapshot,
    event: MemberLoanEvent,
    members: MemberLoanMembers,
    settings: MemberLoanSettings,
) -> MemberLoanNotificationMessage:
    proposer = members.by_username(event.proposed_by_username) or members.lender
    counterparty = members.other_than(proposer)
    change_name = plain_event_name(event.event_type, members)
    amount_text = f" of {format_money(Decimal(event.amount))}" if event.amount is not None else ""
    when = format_long_date(event.effective_date)
    decision = snapshot.decisions_by_event_id.get(event.id)

    if kind == NOTIFICATION_PROPOSED:
        recipients_members: tuple[MemberLoanMember, ...] = (counterparty,)
        subject = f"Member Loan: {proposer.display_name} proposed a change for your approval"
        intro = (
            f"{proposer.display_name} proposed a change to the Member Loan. Nothing changes until you approve it."
        )
        preview = event.preview_at_proposal
        figures_heading = f"Before and after, on {when}, if you approve:"
    else:
        recipients_members = (members.lender, members.yarden)
        verb = {DECISION_APPROVED: "approved", DECISION_REJECTED: "rejected", DECISION_CANCELLED: "cancelled", DECISION_EXPIRED: "expired"}[kind]
        subject = f"Member Loan: change {verb} - {change_name}{amount_text} on {when}"
        if kind == DECISION_APPROVED:
            intro = f"This change is now part of the loan. It takes effect on {when}."
            preview = (decision.preview_at_decision if decision and decision.preview_at_decision else event.preview_at_proposal)
            figures_heading = f"Before and after, on {when}:"
        else:
            intro = {
                DECISION_REJECTED: "This proposed change was rejected. Nothing changed.",
                DECISION_CANCELLED: "This proposed change was cancelled by the member who proposed it. Nothing changed.",
                DECISION_EXPIRED: "This proposed change expired without a decision. Nothing changed. It can be proposed again.",
            }[kind]
            preview = event.preview_at_proposal
            figures_heading = "What it would have changed (nothing was applied):"

    missing = [m.display_name for m in recipients_members if not m.email]
    if missing:
        raise member_loan_mail_transport.MemberLoanEmailNotSent(f"no e-mail address configured for {', '.join(missing)}")

    detail_lines = _event_detail_lines(snapshot, event, members)
    bucket_rows = _bucket_rows(preview["buckets_before"], preview["buckets_after"], members.lender.display_name)
    warning = YARDEN_INCREASE_WARNING.format(yarden=members.yarden.display_name) if (
        event.event_type == YARDEN_ADDITIONAL_WITHDRAWAL_INCREASE
    ) else None
    approval_link = f"{settings.app_origin}/member-loan/approvals/{event.id}"

    text_lines = [intro, ""] + detail_lines + ["", figures_heading]
    width = max(len(r[0]) for r in bucket_rows)
    text_lines.append(f"{'':{width}}  {'Before':>14}  {'After':>14}")
    text_lines += [f"{label:{width}}  {before:>14}  {after:>14}" for label, before, after in bucket_rows]
    if warning:
        text_lines += ["", warning]
    if kind == NOTIFICATION_PROPOSED:
        text_lines += [
            "",
            f"To approve or reject it, open {approval_link} and sign in with your passkey.",
            "This link does not approve anything by itself.",
        ]
    text_body = "\n".join(text_lines) + "\n"

    esc = html.escape
    table_rows = "".join(
        f"<tr><td style='padding:4px 12px 4px 0'>{esc(label)}</td>"
        f"<td style='padding:4px 12px;text-align:right'>{esc(before)}</td>"
        f"<td style='padding:4px 0 4px 12px;text-align:right'>{esc(after)}</td></tr>"
        for label, before, after in bucket_rows
    )
    html_parts = [
        "<html><body style='font-family:Helvetica,Arial,sans-serif;color:#1f2933;line-height:1.5'>",
        f"<p style='font-size:16px'>{esc(intro)}</p>",
        "<p>" + "<br>".join(esc(line) for line in detail_lines) + "</p>",
        f"<p><strong>{esc(figures_heading)}</strong></p>",
        "<table style='border-collapse:collapse'><tr><th></th><th style='text-align:right;padding:4px 12px'>Before</th>"
        "<th style='text-align:right;padding:4px 0 4px 12px'>After</th></tr>" + table_rows + "</table>",
    ]
    if warning:
        html_parts.append(f"<p style='color:#9a3412'><strong>{esc(warning)}</strong></p>")
    if kind == NOTIFICATION_PROPOSED:
        html_parts.append(
            f"<p><a href='{esc(approval_link, quote=True)}'>Open the change in the app</a> and sign in with your passkey "
            "to approve or reject it. This link does not approve anything by itself.</p>"
        )
    html_parts.append("</body></html>")
    return MemberLoanNotificationMessage(
        recipients=tuple(m.email for m in recipients_members),
        subject=subject,
        text_body=text_body,
        html_body="".join(html_parts),
    )


def send_member_loan_notification_after_commit(kind: str, event_id: UUID) -> None:
    """Background task: compose, send, and record the outcome. Never raises."""

    audit_action = "proposal_notification" if kind == NOTIFICATION_PROPOSED else "decision_notification"
    outcome_action = f"{audit_action}_failed"
    detail: dict = {"kind": kind}
    try:
        with SessionLocal() as db:
            settings = load_member_loan_settings()
            members = load_member_loan_members(db, settings)
            snapshot = load_member_loan_ledger_snapshot(db)
            event = snapshot.events_by_id[event_id]
            message = compose_member_loan_notification(kind, snapshot, event, members, settings)
            detail["recipients"] = list(message.recipients)
        member_loan_mail_transport.deliver_member_loan_email(
            sender_address=settings.sender_address,
            recipients=message.recipients,
            subject=message.subject,
            text_body=message.text_body,
            html_body=message.html_body,
        )
        outcome_action = f"{audit_action}_sent"
    except Exception as error:  # noqa: BLE001 -- a notification must never break the change it reports
        detail["error"] = (str(error) or type(error).__name__)[:200]
        logger.warning("member loan notification %s for %s failed: %s", kind, event_id, type(error).__name__)
    _record_notification_outcome(outcome_action, event_id, detail)


def _record_notification_outcome(action: str, event_id: UUID, detail: dict) -> None:
    try:
        with SessionLocal() as db:
            member_loan_crud.acquire_member_loan_write_lock(db)
            append_member_loan_audit_entry(
                db, actor_user_id=None, actor_username="system", action=action, event_id=event_id, detail=detail
            )
            db.commit()
    except Exception:  # noqa: BLE001
        logger.exception("member loan: could not record %s for %s", action, event_id)


def notification_kind_for_decision(decision: Optional[str]) -> str:
    return decision or NOTIFICATION_PROPOSED
