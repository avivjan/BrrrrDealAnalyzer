"""Reject or cancel a pending proposal (one module: the two share every rule but who may act).
Approving is signing its Loan Change Record (`completeSigning.py`)."""

from typing import Optional
from uuid import UUID

from BL.memberLoan.common.member_loan_access import MemberLoanCaller
from BL.memberLoan.common.member_loan_ledger_service import decide_member_loan_event, load_member_loan_ledger_snapshot
from BL.memberLoan.common.member_loan_outcome import MemberLoanOutcome
from BL.memberLoan.common.member_loan_views import proposal_res


def decide_event(db, caller: MemberLoanCaller, event_id: UUID, decision: str, *, reason: Optional[str] = None) -> MemberLoanOutcome:
    result = decide_member_loan_event(db, caller, event_id, decision, reason=reason)
    snapshot = load_member_loan_ledger_snapshot(db)
    return MemberLoanOutcome(proposal_res(snapshot, snapshot.events_by_id[event_id], caller), [(result.decision, event_id)])
