"""One month's statement: the sent (final) copy if it was sent, otherwise the figures so far."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from BL.memberLoan.common.member_loan_access import MemberLoanCaller
from BL.memberLoan.common.member_loan_engine import first_day_of_month
from BL.memberLoan.common.member_loan_ledger_service import MemberLoanRequestRefused, load_member_loan_ledger_snapshot, member_loan_terms
from BL.memberLoan.common.member_loan_outcome import MemberLoanOutcome
from BL.memberLoan.common import member_loan_settings
from BL.memberLoan.common.member_loan_statement_pdf import render_member_loan_statement_pdf
from BL.memberLoan.common.member_loan_statement_service import build_member_loan_statement_for_month
from DAL.crud import member_loan as member_loan_crud
from ReqRes.common.member_loan_schemas import MemberLoanStatementRes

NOT_FINAL_WARNING = "This month is not final yet: the figures assume nothing else changes before its statement is sent."


def parse_statement_month(month_text: str) -> date:
    try:
        year, month = (int(part) for part in month_text.split("-"))
        return date(year, month, 1)
    except (ValueError, TypeError):
        raise MemberLoanRequestRefused(422, "The month must look like 2026-12.")


def _sent_copy(db, month: date):
    return next((s for s in member_loan_crud.list_member_loan_statement_sends(db, month) if not s.is_dry_run and s.status == "sent"), None)


def statement_document_and_send(db, caller: MemberLoanCaller, month_text: str) -> tuple[dict, Optional[object]]:
    month = parse_statement_month(month_text)
    terms = member_loan_terms()
    current_month = first_day_of_month(member_loan_settings.new_york_today() + timedelta(days=1))
    if not (terms.loan_effective_date <= month <= current_month):
        raise MemberLoanRequestRefused(422, "There is no statement for that month.")
    sent = _sent_copy(db, month)
    if sent is not None:
        return sent.statement_snapshot, sent
    snapshot = load_member_loan_ledger_snapshot(db)
    document = build_member_loan_statement_for_month(snapshot, caller.members, month).as_plain_dict()
    document["warnings"] = [NOT_FINAL_WARNING] + document["warnings"]
    return document, None


def sent_line_for(sent) -> Optional[str]:
    if sent is None:
        return None
    return (
        f"Sent on {sent.sent_at:%b %d, %Y} to {', '.join(sent.recipients)}. "
        f"Objections must be made in writing by {sent.objection_deadline:%b %d, %Y}."
    )


def get_statement(db, caller: MemberLoanCaller, month_text: str) -> MemberLoanOutcome:
    document, sent = statement_document_and_send(db, caller, month_text)
    return MemberLoanOutcome(
        MemberLoanStatementRes(
            statement_month=document["statement_month"],
            document=document,
            is_final=sent is not None,
            sent_at=sent.sent_at if sent else None,
            objection_deadline=sent.objection_deadline if sent else None,
            sent_to=list(sent.recipients) if sent else [],
        )
    )


def get_statement_pdf(db, caller: MemberLoanCaller, month_text: str) -> tuple[bytes, str]:
    document, sent = statement_document_and_send(db, caller, month_text)
    return render_member_loan_statement_pdf(document, sent_line=sent_line_for(sent)), f"member-loan-statement-{document['statement_month']}.pdf"
