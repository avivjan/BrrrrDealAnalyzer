"""Passkey options for a signing, with the challenge bound to the document's SHA-256."""

from uuid import UUID

from BL.memberLoan.common.member_loan_access import MemberLoanCaller
from BL.memberLoan.common.member_loan_outcome import MemberLoanOutcome
from BL.memberLoan.common.member_loan_signing_service import begin_signing_passkey
from ReqRes.common.member_loan_schemas import MemberLoanPasskeySigningOptionsRes


def begin_signing_passkey_ceremony(db, caller: MemberLoanCaller, signing_request_id: UUID) -> MemberLoanOutcome:
    options = begin_signing_passkey(db, caller, signing_request_id)
    return MemberLoanOutcome(MemberLoanPasskeySigningOptionsRes(passkey_challenge_id=str(options.challenge_id), options=options.options_json))
