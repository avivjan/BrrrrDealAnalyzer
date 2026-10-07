"""Member Loan request and response models.

Money crosses the API as text with two decimals ("1000.00"), never as a JSON
number, so no floating point is involved anywhere between the form and the
engine. Every date is explicit: the device sends its own "today" (D3).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

MONEY_TEXT_PATTERN = r"^\d{1,8}(\.\d{1,2})?$"
FINGERPRINT_PATTERN = r"^[0-9a-f]{64}$"

ProposableEventType = Literal[
    "lender_withdrawal",
    "lender_additional_advance",
    "yarden_capital_contribution_reduction",
    "yarden_additional_withdrawal_increase",
    "interest_payment_election",
]
ProposalState = Literal["pending", "approved", "rejected", "cancelled", "expired"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class MemberLoanProposalCreateReq(_Strict):
    event_type: ProposableEventType
    effective_date: date
    amount: Optional[str] = Field(default=None, pattern=MONEY_TEXT_PATTERN)
    interest_election_choice: Optional[Literal["reinvest", "cash"]] = None
    written_agreement_date: Optional[date] = None
    written_agreement_description: Optional[str] = Field(default=None, max_length=500)
    payment_reference: Optional[str] = Field(default=None, max_length=200)
    note: Optional[str] = Field(default=None, max_length=1000)


class MemberLoanReversalProposalReq(_Strict):
    reason: str = Field(min_length=3, max_length=500)
    note: Optional[str] = Field(default=None, max_length=1000)


class MemberLoanApprovalReq(_Strict):
    preview_fingerprint: str = Field(pattern=FINGERPRINT_PATTERN)


class MemberLoanRejectionReq(_Strict):
    reason: str = Field(min_length=1, max_length=500)


class MemberLoanBucketsRes(BaseModel):
    original_principal: str
    capitalized_interest: str
    total_balance: str
    accrued_interest: str
    interest_payable: str
    amount_owed: str
    lender_capital_credited: str


class MemberLoanAllocationRes(BaseModel):
    from_interest_payable: str
    from_accrued_interest: str
    from_capitalized_interest: str
    from_original_principal: str


class MemberLoanPreviewRes(BaseModel):
    effective_date: date
    buckets_before: MemberLoanBucketsRes
    buckets_after: MemberLoanBucketsRes
    allocation: Optional[MemberLoanAllocationRes] = None
    preview_fingerprint: str


class MemberLoanAccessRes(BaseModel):
    allowed: bool
    username: str
    display_name: str
    role: Literal["lender", "yarden"]
    other_member_display_name: str
    proposals_waiting_for_you: int


class MemberLoanSummaryRes(BaseModel):
    as_of_date: date
    buckets: MemberLoanBucketsRes
    loan_effective_date: date
    maturity_date: date
    original_principal_at_start: str
    proposals_waiting_for_you: int
    proposals_waiting_for_other_member: int


class MemberLoanProposalRes(BaseModel):
    id: str
    proposal_sequence: int
    event_type: str
    plain_event_name: str
    effective_date: date
    amount: Optional[str] = None
    interest_election_choice: Optional[str] = None
    written_agreement_date: Optional[date] = None
    written_agreement_description: Optional[str] = None
    payment_reference: Optional[str] = None
    note: Optional[str] = None
    reverses_event_id: Optional[str] = None
    reversed_event_summary: Optional[str] = None
    reversal_reason: Optional[str] = None
    state: ProposalState
    proposed_by_display_name: str
    proposed_at: datetime
    decided_by_display_name: Optional[str] = None
    decided_at: Optional[datetime] = None
    decision_reason: Optional[str] = None
    preview_at_proposal: MemberLoanPreviewRes
    live_preview: Optional[MemberLoanPreviewRes] = None
    live_preview_problem: Optional[str] = None
    figures_changed_since_proposal: bool = False
    caller_may_approve_or_reject: bool = False
    caller_may_cancel: bool = False
    caller_may_propose_reversal: bool = False
    includes_yarden_increase_warning: bool = False


class MemberLoanLedgerRowRes(BaseModel):
    row_date: date
    row_kind: str
    plain_description: str
    event_id: Optional[str] = None
    amount: Optional[str] = None
    allocation: Optional[MemberLoanAllocationRes] = None
    interest_added_to_debt: Optional[str] = None
    interest_moved_to_interest_payable: Optional[str] = None
    buckets_after: MemberLoanBucketsRes
    proposed_by_display_name: Optional[str] = None
    approved_by_display_name: Optional[str] = None


class MemberLoanLedgerRes(BaseModel):
    through_date: date
    rows: list[MemberLoanLedgerRowRes]


class MemberLoanStatementRes(BaseModel):
    statement_month: str
    document: dict
    is_final: bool
    sent_at: Optional[datetime] = None
    objection_deadline: Optional[date] = None
    sent_to: list[str] = []


class MemberLoanAuditEntryRes(BaseModel):
    audit_sequence: int
    recorded_at: datetime
    actor_display_name: str
    action: str
    event_id: Optional[str] = None
    state_before: Optional[dict] = None
    state_after: Optional[dict] = None
    detail: Optional[dict] = None


class MemberLoanIntegrityRes(BaseModel):
    intact: bool
    problems: list[str]
    proposals_checked: int
    decisions_checked: int
    audit_entries_checked: int


class MemberLoanExplanationRes(BaseModel):
    lines: list[str]
