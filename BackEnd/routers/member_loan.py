"""/member-loan/* -- the Member Loan between Aviv (Lender) and Big Whales AY LLC.

Self-gated (`BL/memberLoan/common/member_loan_access.py`): every route needs a
passkey web session of one of the two members whatever AUTH_MODE says, and
every write also needs CSRF, a fresh passkey assertion and the rate limit.
Never an MCP tool (`mcp_server.EXCLUDED_PREFIXES`).

Each handler first expires stale proposals and schedules their e-mails, then
delegates to `BL/memberLoan/<endpoint>.py`. A refusal is returned as a JSON
response (not raised) so the e-mails scheduled after commit still go out.
"""

from __future__ import annotations

from datetime import date
from typing import Callable, List, Literal, Optional
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Path, Query
from fastapi.responses import JSONResponse, Response
from sqlalchemy.orm import Session

from BL.memberLoan.checkIntegrity import check_integrity
from BL.memberLoan.common.member_loan_access import MemberLoanCaller, require_member_loan_reader, require_member_loan_writer
from BL.memberLoan.common.member_loan_ledger_service import (
    DECISION_APPROVED,
    DECISION_CANCELLED,
    DECISION_REJECTED,
    MemberLoanRequestRefused,
)
from BL.memberLoan.common.member_loan_notifications import send_member_loan_notification_after_commit
from BL.memberLoan.common.member_loan_outcome import MemberLoanOutcome, expire_and_list_notifications
from BL.memberLoan.decideEvent import decide_event
from BL.memberLoan.exportLedgerCsv import export_ledger_csv
from BL.memberLoan.getAccess import get_member_loan_access
from BL.memberLoan.getEvent import get_event
from BL.memberLoan.getExplanation import get_explanation
from BL.memberLoan.getLedger import get_member_loan_ledger
from BL.memberLoan.getStatement import get_statement, get_statement_pdf
from BL.memberLoan.getSummary import get_member_loan_summary
from BL.memberLoan.listAudit import list_audit
from BL.memberLoan.listEvents import list_events
from BL.memberLoan.proposeEvent import propose_event
from BL.memberLoan.proposeReversal import propose_reversal
from db import get_db
from ReqRes.common.member_loan_schemas import (
    MemberLoanAccessRes,
    MemberLoanApprovalReq,
    MemberLoanAuditEntryRes,
    MemberLoanExplanationRes,
    MemberLoanIntegrityRes,
    MemberLoanLedgerRes,
    MemberLoanProposalCreateReq,
    MemberLoanProposalRes,
    MemberLoanRejectionReq,
    MemberLoanReversalProposalReq,
    MemberLoanStatementRes,
    MemberLoanSummaryRes,
)

router = APIRouter()

STATEMENT_MONTH_PATH_PATTERN = r"^\d{4}-\d{2}$"


def _refusal_response(refused: MemberLoanRequestRefused, background_tasks: BackgroundTasks) -> JSONResponse:
    detail = {"message": refused.plain_language_reason, "code": refused.code, **refused.extra}
    return JSONResponse(status_code=refused.status_code, content={"detail": detail}, background=background_tasks)


def _run(db: Session, background_tasks: BackgroundTasks, endpoint: Callable[[], MemberLoanOutcome]):
    for kind, event_id in expire_and_list_notifications(db):
        background_tasks.add_task(send_member_loan_notification_after_commit, kind, event_id)
    try:
        outcome = endpoint()
    except MemberLoanRequestRefused as refused:
        db.rollback()
        return _refusal_response(refused, background_tasks)
    for kind, event_id in outcome.notifications_after_commit:
        background_tasks.add_task(send_member_loan_notification_after_commit, kind, event_id)
    return outcome.response


def _file(db: Session, background_tasks: BackgroundTasks, endpoint: Callable[[], tuple], media_type: str):
    for kind, event_id in expire_and_list_notifications(db):
        background_tasks.add_task(send_member_loan_notification_after_commit, kind, event_id)
    try:
        content, filename = endpoint()
    except MemberLoanRequestRefused as refused:
        return _refusal_response(refused, background_tasks)
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"', "Cache-Control": "no-store"},
        background=background_tasks,
    )


@router.get("/member-loan/access", response_model=MemberLoanAccessRes)
def member_loan_access(background_tasks: BackgroundTasks, db: Session = Depends(get_db), caller: MemberLoanCaller = Depends(require_member_loan_reader)):
    return _run(db, background_tasks, lambda: get_member_loan_access(db, caller))


@router.get("/member-loan/summary", response_model=MemberLoanSummaryRes)
def member_loan_summary(
    background_tasks: BackgroundTasks,
    as_of_date: date = Query(..., description="The device's date: the server never guesses 'today'."),
    db: Session = Depends(get_db),
    caller: MemberLoanCaller = Depends(require_member_loan_reader),
):
    return _run(db, background_tasks, lambda: get_member_loan_summary(db, caller, as_of_date))


@router.get("/member-loan/ledger", response_model=MemberLoanLedgerRes)
def member_loan_ledger(
    background_tasks: BackgroundTasks,
    through_date: date = Query(...),
    db: Session = Depends(get_db),
    caller: MemberLoanCaller = Depends(require_member_loan_reader),
):
    return _run(db, background_tasks, lambda: get_member_loan_ledger(db, caller, through_date))


@router.get("/member-loan/ledger.csv")
def member_loan_ledger_csv(
    background_tasks: BackgroundTasks,
    through_date: date = Query(...),
    db: Session = Depends(get_db),
    caller: MemberLoanCaller = Depends(require_member_loan_reader),
):
    return _file(db, background_tasks, lambda: export_ledger_csv(db, caller, through_date), "text/csv; charset=utf-8")


@router.post("/member-loan/events", response_model=MemberLoanProposalRes, status_code=201)
def member_loan_propose_event(
    request: MemberLoanProposalCreateReq,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    caller: MemberLoanCaller = Depends(require_member_loan_writer),
):
    return _run(db, background_tasks, lambda: propose_event(db, caller, request))


@router.get("/member-loan/events", response_model=List[MemberLoanProposalRes])
def member_loan_list_events(
    background_tasks: BackgroundTasks,
    state: Optional[Literal["pending", "approved", "rejected", "cancelled", "expired"]] = None,
    db: Session = Depends(get_db),
    caller: MemberLoanCaller = Depends(require_member_loan_reader),
):
    return _run(db, background_tasks, lambda: list_events(db, caller, state))


@router.get("/member-loan/events/{event_id}", response_model=MemberLoanProposalRes)
def member_loan_get_event(
    event_id: UUID, background_tasks: BackgroundTasks, db: Session = Depends(get_db), caller: MemberLoanCaller = Depends(require_member_loan_reader)
):
    return _run(db, background_tasks, lambda: get_event(db, caller, event_id))


@router.post("/member-loan/events/{event_id}/reversal", response_model=MemberLoanProposalRes, status_code=201)
def member_loan_propose_reversal(
    event_id: UUID,
    request: MemberLoanReversalProposalReq,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    caller: MemberLoanCaller = Depends(require_member_loan_writer),
):
    return _run(db, background_tasks, lambda: propose_reversal(db, caller, event_id, request))


@router.post("/member-loan/events/{event_id}/approval", response_model=MemberLoanProposalRes)
def member_loan_approve_event(
    event_id: UUID,
    request: MemberLoanApprovalReq,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    caller: MemberLoanCaller = Depends(require_member_loan_writer),
):
    return _run(db, background_tasks, lambda: decide_event(db, caller, event_id, DECISION_APPROVED, preview_fingerprint=request.preview_fingerprint))


@router.post("/member-loan/events/{event_id}/rejection", response_model=MemberLoanProposalRes)
def member_loan_reject_event(
    event_id: UUID,
    request: MemberLoanRejectionReq,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    caller: MemberLoanCaller = Depends(require_member_loan_writer),
):
    return _run(db, background_tasks, lambda: decide_event(db, caller, event_id, DECISION_REJECTED, reason=request.reason))


@router.post("/member-loan/events/{event_id}/cancellation", response_model=MemberLoanProposalRes)
def member_loan_cancel_event(
    event_id: UUID, background_tasks: BackgroundTasks, db: Session = Depends(get_db), caller: MemberLoanCaller = Depends(require_member_loan_writer)
):
    return _run(db, background_tasks, lambda: decide_event(db, caller, event_id, DECISION_CANCELLED))


@router.get("/member-loan/statements/{statement_month}", response_model=MemberLoanStatementRes)
def member_loan_statement(
    background_tasks: BackgroundTasks,
    statement_month: str = Path(..., pattern=STATEMENT_MONTH_PATH_PATTERN),
    db: Session = Depends(get_db),
    caller: MemberLoanCaller = Depends(require_member_loan_reader),
):
    return _run(db, background_tasks, lambda: get_statement(db, caller, statement_month))


@router.get("/member-loan/statements/{statement_month}/pdf")
def member_loan_statement_pdf(
    background_tasks: BackgroundTasks,
    statement_month: str = Path(..., pattern=STATEMENT_MONTH_PATH_PATTERN),
    db: Session = Depends(get_db),
    caller: MemberLoanCaller = Depends(require_member_loan_reader),
):
    return _file(db, background_tasks, lambda: get_statement_pdf(db, caller, statement_month), "application/pdf")


@router.get("/member-loan/audit", response_model=List[MemberLoanAuditEntryRes])
def member_loan_audit(background_tasks: BackgroundTasks, db: Session = Depends(get_db), caller: MemberLoanCaller = Depends(require_member_loan_reader)):
    return _run(db, background_tasks, lambda: list_audit(db, caller))


@router.get("/member-loan/integrity", response_model=MemberLoanIntegrityRes)
def member_loan_integrity(background_tasks: BackgroundTasks, db: Session = Depends(get_db), caller: MemberLoanCaller = Depends(require_member_loan_reader)):
    return _run(db, background_tasks, lambda: check_integrity(db, caller))


@router.get("/member-loan/explanation", response_model=MemberLoanExplanationRes)
def member_loan_explanation(background_tasks: BackgroundTasks, db: Session = Depends(get_db), caller: MemberLoanCaller = Depends(require_member_loan_reader)):
    return _run(db, background_tasks, lambda: get_explanation(db, caller))
