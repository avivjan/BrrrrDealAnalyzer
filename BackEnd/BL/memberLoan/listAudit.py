from BL.memberLoan.common.member_loan_access import MemberLoanCaller
from BL.memberLoan.common.member_loan_outcome import MemberLoanOutcome
from DAL.crud import member_loan as member_loan_crud
from ReqRes.common.member_loan_schemas import MemberLoanAuditEntryRes

AUDIT_ENTRIES_SHOWN = 500


def list_audit(db, caller: MemberLoanCaller) -> MemberLoanOutcome:
    entries = member_loan_crud.list_member_loan_audit_entries(db, newest_first=True, limit=AUDIT_ENTRIES_SHOWN)
    return MemberLoanOutcome([
        MemberLoanAuditEntryRes(
            audit_sequence=e.audit_sequence,
            recorded_at=e.recorded_at,
            actor_display_name="the system" if e.actor_user_id is None and e.actor_username == "system" else caller.members.display_name_for(e.actor_username),
            action=e.action,
            event_id=str(e.event_id) if e.event_id else None,
            state_before=e.state_before,
            state_after=e.state_after,
            detail=e.detail,
        )
        for e in entries
    ])
