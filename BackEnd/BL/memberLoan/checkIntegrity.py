from BL.memberLoan.common.member_loan_access import MemberLoanCaller
from BL.memberLoan.common.member_loan_hash_chain import verify_hash_chain
from BL.memberLoan.common.member_loan_outcome import MemberLoanOutcome
from DAL.crud import member_loan as member_loan_crud
from ReqRes.common.member_loan_schemas import MemberLoanIntegrityRes


def check_integrity(db, caller: MemberLoanCaller) -> MemberLoanOutcome:
    events = member_loan_crud.list_member_loan_events(db)
    decisions = member_loan_crud.list_member_loan_event_decisions(db)
    audit_entries = member_loan_crud.list_member_loan_audit_entries(db)
    problems = (
        verify_hash_chain(events, hash_column_name="event_hash", previous_hash_column_name="previous_event_hash", table_label="Proposal")
        + verify_hash_chain(decisions, hash_column_name="decision_hash", previous_hash_column_name="previous_decision_hash", table_label="Decision")
        + verify_hash_chain(audit_entries, hash_column_name="audit_hash", previous_hash_column_name="previous_audit_hash", table_label="Audit")
    )
    return MemberLoanOutcome(
        MemberLoanIntegrityRes(
            intact=not problems,
            problems=problems,
            proposals_checked=len(events),
            decisions_checked=len(decisions),
            audit_entries_checked=len(audit_entries),
        )
    )
