from BL.memberLoan.common.member_loan_access import MemberLoanCaller
from BL.memberLoan.common.member_loan_ledger_service import load_member_loan_ledger_snapshot, proposals_waiting_for
from BL.memberLoan.common.member_loan_outcome import MemberLoanOutcome
from ReqRes.common.member_loan_schemas import MemberLoanAccessRes


def get_member_loan_access(db, caller: MemberLoanCaller) -> MemberLoanOutcome:
    snapshot = load_member_loan_ledger_snapshot(db)
    return MemberLoanOutcome(
        MemberLoanAccessRes(
            allowed=True,
            username=caller.member.username,
            display_name=caller.member.display_name,
            role=caller.member.role,
            other_member_display_name=caller.other_member.display_name,
            proposals_waiting_for_you=proposals_waiting_for(snapshot, caller.member.username),
        ),
    )
