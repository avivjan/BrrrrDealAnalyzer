"""Request and response shapes of /liquidity/construction-accounts/* (tasks/todo/ConstructionAccountPerRehab.md).

Amounts are exact dollars. A Mercury account is named by its id, its name and the last four digits of its number:
the full number never reaches a response.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field

MAX_CONSTRUCTION_ACCOUNT_AMOUNT_DOLLARS = 50_000_000
MercuryAccountId = Field(..., min_length=1, max_length=80, pattern=r"^[A-Za-z0-9-]+$")

ConstructionAccountManualAdjustmentType = Literal["manual_payment", "manual_draw"]
ConstructionAccountTransactionCategory = Literal["loan_draw", "rehab_payment", "own_money"]


def _amount(description: str, default=...):
    return Field(default, ge=0, le=MAX_CONSTRUCTION_ACCOUNT_AMOUNT_DOLLARS, description=description)


class ConstructionAccountLinkReq(BaseModel):
    """Link a construction account to a Bought BRRRR deal, or edit the link: every field stays editable at any time."""
    construction_mercury_account_id: str = MercuryAccountId
    primary_checking_mercury_account_id: str = MercuryAccountId
    loan_draws_pulled_before_construction_account_dollars: float = _amount(
        "Loan draws already pulled before this account existed (0 for a rehab that starts with the account).", 0)
    rehab_payments_made_before_construction_account_dollars: float = _amount(
        "Rehab payments already made before this account existed.", 0)
    planned_deposit_override_dollars: Optional[float] = _amount(
        "Your own deposit target. Null = the formula: rehab cushion + the rehab beyond the construction budget.", None)
    minimum_balance_to_keep_in_construction_account_dollars: float = _amount(
        "A float to keep in the account (reimbursement draws); it lowers what is safe to steal.", 0)


class ConstructionAccountSwitchReq(BaseModel):
    """Replace the deal's construction account mid-rehab. The old account's draws and payments move into the baselines."""
    new_construction_mercury_account_id: str = MercuryAccountId
    loan_draws_pulled_before_construction_account_dollars: float = _amount("Draws pulled before the new account (prefilled by the preview).")
    rehab_payments_made_before_construction_account_dollars: float = _amount("Rehab payments made before the new account (prefilled by the preview).")


class ConstructionAccountSwitchPreviewRes(BaseModel):
    old_construction_account_balance_dollars: float
    old_account_must_be_emptied_first: bool
    loan_draws_pulled_before_construction_account_dollars: float = Field(..., description="The current baseline + the old account's categorised draws.")
    rehab_payments_made_before_construction_account_dollars: float = Field(..., description="The current baseline + the old account's categorised rehab payments.")


class ConstructionAccountManualAdjustmentReq(BaseModel):
    """Rehab money that never touched the construction account."""
    adjustment_type: ConstructionAccountManualAdjustmentType
    amount_dollars: float = Field(..., gt=0, le=MAX_CONSTRUCTION_ACCOUNT_AMOUNT_DOLLARS)
    date: date
    note: Optional[str] = Field(None, max_length=500)


class ConstructionAccountManualAdjustmentRes(BaseModel):
    id: str
    adjustment_type: ConstructionAccountManualAdjustmentType
    amount_dollars: float
    date: date
    note: Optional[str] = None


class ConstructionAccountTransactionOverrideReq(BaseModel):
    ignored: bool = False
    category_override: Optional[ConstructionAccountTransactionCategory] = None
    note: Optional[str] = Field(None, max_length=500)


class ConstructionAccountTransactionRes(BaseModel):
    mercury_transaction_id: str
    transaction_date: Optional[date] = None
    counterparty_name: str
    signed_amount_dollars: float = Field(..., description="Positive = into the construction account.")
    bank_status: str
    automatic_category: ConstructionAccountTransactionCategory
    ignored: bool
    category_override: Optional[ConstructionAccountTransactionCategory] = None
    note: Optional[str] = None
    effective_category: Optional[ConstructionAccountTransactionCategory] = Field(
        None, description="Null = counts for nothing: ignored by hand, or failed / cancelled at the bank.")


class ConstructionAccountRefreshReq(BaseModel):
    today: Optional[date] = Field(None, description="The browser's local date; default: today in the liquidity settings' time zone.")


class MercuryAccountNameRes(BaseModel):
    mercury_account_id: str
    name: str
    account_number_last_four: str


class ConstructionAccountSumBySourceRes(BaseModel):
    from_the_bank_feed_dollars: float
    before_this_account_dollars: float
    entered_by_hand_dollars: float
    total_dollars: float


class ConstructionAccountStatusRes(BaseModel):
    """One Bought BRRRR deal on the Construction Accounts page: its link, and every number with its source."""
    bought_deal_id: str
    deal_address: str
    is_linked: bool
    rows_wait_for_a_resync: bool = Field(..., description="The deal is 'liquidity out of date': its three construction rows follow after the Re-sync.")
    rehab_completed_is_approved: bool
    construction_budget_dollars: float
    rehab_cost_dollars: float
    rehab_cushion_dollars: float
    original_steal_dollars: float
    # --- only when linked -------------------------------------------------------------------------------------
    mercury_workspace_label: Optional[str] = None
    construction_account: Optional[MercuryAccountNameRes] = None
    primary_checking_account: Optional[MercuryAccountNameRes] = None
    previous_construction_mercury_account_ids: List[str] = Field(default_factory=list)
    amounts_as_of: Optional[datetime] = Field(None, description="When the bank amounts were last read from Mercury; null = never.")
    mercury_is_unavailable: bool = False
    current_balance_dollars: Optional[float] = None
    available_balance_dollars: Optional[float] = None
    loan_draws_pulled: Optional[ConstructionAccountSumBySourceRes] = None
    loan_draws_remaining_to_pull_dollars: Optional[float] = None
    rehab_payments_made: Optional[ConstructionAccountSumBySourceRes] = None
    unpaid_rehab_remaining_dollars: Optional[float] = None
    own_money_transferred_into_the_account_dollars: Optional[float] = None
    own_money_transferred_out_of_the_account_dollars: Optional[float] = None
    planned_deposit_dollars: Optional[float] = None
    planned_deposit_by_the_formula_dollars: Optional[float] = None
    planned_deposit_override_dollars: Optional[float] = None
    remaining_deposit_dollars: Optional[float] = None
    minimum_balance_to_keep_in_construction_account_dollars: Optional[float] = None
    projected_return_at_rehab_end_dollars: Optional[float] = None
    safe_to_steal_now_dollars: Optional[float] = None
    top_up_needed_dollars: Optional[float] = None
    loan_draws_pulled_before_construction_account_dollars: Optional[float] = None
    rehab_payments_made_before_construction_account_dollars: Optional[float] = None
    marked_ready_for_close_out_at: Optional[datetime] = None
    closed_out_at: Optional[datetime] = None
    manual_adjustments: List[ConstructionAccountManualAdjustmentRes] = Field(default_factory=list)


class ConstructionAccountClosedOutRes(BaseModel):
    status: ConstructionAccountStatusRes
    balance_left_in_the_account_dollars: float = Field(..., description="Not $0: move it to checking in Mercury (or Reopen).")


class ConstructionAccountRefreshRes(BaseModel):
    refreshed_deal_count: int
    changed_row_count: int
    mercury_is_unavailable: bool
