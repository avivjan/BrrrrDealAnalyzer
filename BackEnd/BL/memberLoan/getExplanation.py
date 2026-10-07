from BL.memberLoan.common.member_loan_access import MemberLoanCaller
from BL.memberLoan.common.member_loan_ledger_service import member_loan_terms
from BL.memberLoan.common.member_loan_outcome import MemberLoanOutcome
from BL.memberLoan.common.member_loan_statement_document import member_loan_how_it_works_lines
from ReqRes.common.member_loan_schemas import MemberLoanExplanationRes


def get_explanation(db, caller: MemberLoanCaller) -> MemberLoanOutcome:
    lines = member_loan_how_it_works_lines(member_loan_terms(), caller.members.lender.display_name, caller.members.yarden.display_name)
    return MemberLoanOutcome(MemberLoanExplanationRes(lines=list(lines)))
