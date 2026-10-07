from datetime import date

from BL.memberLoan.common.member_loan_access import MemberLoanCaller
from BL.memberLoan.common.member_loan_ledger_service import (
    load_member_loan_ledger_snapshot,
    member_loan_position_as_of,
    member_loan_terms,
    proposals_waiting_for,
    proposals_waiting_for_other_member,
)
from BL.memberLoan.common.member_loan_outcome import MemberLoanOutcome
from BL.memberLoan.common.member_loan_views import buckets_res
from ReqRes.common.member_loan_schemas import MemberLoanSummaryRes


def get_member_loan_summary(db, caller: MemberLoanCaller, as_of_date: date) -> MemberLoanOutcome:
    snapshot = load_member_loan_ledger_snapshot(db)
    position = member_loan_position_as_of(snapshot, as_of_date)
    terms = member_loan_terms()
    return MemberLoanOutcome(
        MemberLoanSummaryRes(
            as_of_date=as_of_date,
            buckets=buckets_res(position.buckets),
            loan_effective_date=terms.loan_effective_date,
            maturity_date=terms.maturity_date,
            original_principal_at_start=f"{terms.original_principal_at_start:.2f}",
            proposals_waiting_for_you=proposals_waiting_for(snapshot, caller.member.username),
            proposals_waiting_for_other_member=proposals_waiting_for_other_member(snapshot, caller.member.username),
        ),
    )
