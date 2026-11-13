"""Request and response shapes of /liquidity/construction-accounts/* (tasks/todo/ConstructionAccountPerRehab.md).

Amounts are exact dollars. A Mercury account is named by its id, its name and the last four digits of its number:
the full number never reaches a response.

Every write answers a `ConstructionAccountWriteRes`: the deal's status before and after, and the liquidity rows the
write changes. With `preview_only` the same answer comes back and nothing is saved: it is what the confirmation
prompt shows.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, model_validator

from ReqRes.common.liquidity_deal_schemas import DealCashRowChangesRes

MAX_CONSTRUCTION_ACCOUNT_AMOUNT_DOLLARS = 50_000_000
MercuryAccountId = Field(..., min_length=1, max_length=80, pattern=r"^[A-Za-z0-9-]+$")

ConstructionAccountManualAdjustmentType = Literal["manual_payment", "manual_draw"]
ConstructionAccountTransactionCategory = Literal["loan_draw", "rehab_payment", "own_money"]
SafeToStealCap = Literal["available_balance", "buffer_to_keep", "projected_return"]


def _amount(description: str, default=...):
    return Field(default, ge=0, le=MAX_CONSTRUCTION_ACCOUNT_AMOUNT_DOLLARS, description=description)


# --- Requests -----------------------------------------------------------------------------------------------------

class ConstructionAccountLinkReq(BaseModel):
    """Link a construction account to a Bought BRRRR deal, or edit the link: every field stays editable at any time.
    There is no deposit target here: what goes into the account is the deal's rehab cushion (plus any rehab beyond
    the construction budget)."""
    construction_mercury_account_id: str = MercuryAccountId
    primary_checking_mercury_account_id: str = MercuryAccountId
    loan_draws_pulled_before_construction_account_dollars: float = _amount(
        "Loan draws already pulled before this account existed (0 for a rehab that starts with the account).", 0)
    rehab_payments_made_before_construction_account_dollars: float = _amount(
        "Rehab payments already made before this account existed.", 0)
    minimum_balance_to_keep_in_construction_account_dollars: float = _amount(
        "A float to keep in the account (reimbursement draws); it lowers what is safe to steal.", 0)


class ConstructionAccountRehabFiguresReq(BaseModel):
    """The rehab figures of the Bought deal, edited from its construction account card. Only the fields sent change;
    they are validated and written exactly like a save of the deal itself."""
    actual_rehab_cost_dollars: Optional[float] = _amount("The deal's actual rehab cost, before the contingency.", None)
    rehab_contingency_percent: Optional[float] = Field(None, ge=0, le=100, description="The contingency added on top of the actual rehab cost.")
    construction_budget_dollars: Optional[float] = _amount("The lender's construction loan budget.", None)
    rehab_cushion_dollars: Optional[float] = _amount(
        "The rehab cushion: the one deposit figure. What you deposit into the account is this, plus any rehab beyond the budget.", None)

    @model_validator(mode="after")
    def _at_least_one_figure_is_sent(self) -> "ConstructionAccountRehabFiguresReq":
        if not self.model_fields_set & {"actual_rehab_cost_dollars", "rehab_contingency_percent", "construction_budget_dollars",
                                        "rehab_cushion_dollars"}:
            raise ValueError("Send at least one rehab figure to change.")
        return self


class ConstructionAccountSwitchReq(BaseModel):
    """Replace the deal's construction account mid-rehab. The old account's draws and payments move into the baselines."""
    new_construction_mercury_account_id: str = MercuryAccountId
    loan_draws_pulled_before_construction_account_dollars: float = _amount("Draws pulled before the new account (prefilled by the preview).")
    rehab_payments_made_before_construction_account_dollars: float = _amount("Rehab payments made before the new account (prefilled by the preview).")


class ConstructionAccountManualAdjustmentReq(BaseModel):
    """Rehab money that never touched the construction account."""
    adjustment_type: ConstructionAccountManualAdjustmentType
    amount_dollars: float = Field(..., gt=0, le=MAX_CONSTRUCTION_ACCOUNT_AMOUNT_DOLLARS)
    date: date
    note: Optional[str] = Field(None, max_length=500)


class ConstructionAccountTransactionOverrideReq(BaseModel):
    ignored: bool = False
    category_override: Optional[ConstructionAccountTransactionCategory] = None
    note: Optional[str] = Field(None, max_length=500)


class ConstructionAccountRefreshReq(BaseModel):
    today: Optional[date] = Field(None, description="The browser's local date; default: today in the liquidity settings' time zone.")
    is_a_background_poll: bool = Field(False, description="True for an open page's automatic poll: audited only when it changes something or fails.")


# --- The page -----------------------------------------------------------------------------------------------------

class ConstructionAccountTransferReq(BaseModel):
    """A Deposit (checking -> construction account) or a Steal (construction account -> checking). The two accounts
    are always the ones linked to the deal: the request cannot name an account."""
    amount_dollars: float = Field(..., gt=0, le=MAX_CONSTRUCTION_ACCOUNT_AMOUNT_DOLLARS)
    idempotency_key: str = Field(..., min_length=8, max_length=80, pattern=r"^[A-Za-z0-9-]+$",
                                 description="One per open transfer window: the same key never makes a second transfer.")
    confirm_amount_exceeds_safe_to_steal: bool = Field(
        False, description="A Steal above 'safe to steal now' is refused (409) unless this confirms the top-up it will need.")


class ConstructionAccountTransferRes(BaseModel):
    transfer_id: str
    transfer_direction: Literal["deposit_into_construction_account", "steal_to_primary_checking"]
    amount_dollars: float
    transfer_outcome: Literal["being_sent", "accepted_by_mercury", "refused_by_mercury", "mercury_did_not_answer",
                              "failed_or_cancelled_at_mercury"]
    mercury_transfer_status: Optional[str] = Field(None, description="pending / sent / cancelled / failed / unknown, as Mercury said.")
    mercury_refusal_http_status: Optional[int] = Field(
        None, description="Mercury refused it: the HTTP status it answered (401/403 the token, 400/422 the request, 429 slow down).")
    requested_at: datetime
    is_in_the_bank_feed: bool = Field(..., description="The bank feed shows it (it then counts from the feed, once).")


class MercuryAccountNameRes(BaseModel):
    mercury_account_id: str
    name: str
    account_number_last_four: str


class ConstructionAccountSumBySourceRes(BaseModel):
    from_the_bank_feed_dollars: float
    before_this_account_dollars: float
    entered_by_hand_dollars: float
    total_dollars: float


class ConstructionAccountDatedAmountRes(BaseModel):
    date: date
    amount_dollars: float
    counterparty_name: str = ""


class ConstructionAccountPayeeTotalRes(BaseModel):
    payee_name: str
    amount_dollars: float


class ConstructionAccountTimelineRowRes(BaseModel):
    """One of the deal's rows as the liquidity timeline has it."""
    item_key: str
    transaction_id: str
    description: str
    effective_date: date
    amount_dollars: float
    is_done: bool
    is_overdue: bool


class ConstructionAccountManualAdjustmentRes(BaseModel):
    id: str
    adjustment_type: ConstructionAccountManualAdjustmentType
    amount_dollars: float
    date: date
    note: Optional[str] = None


class ConstructionAccountStatusRes(BaseModel):
    """One Bought BRRRR deal on the Construction Accounts page: every number tied to its construction account, each
    with its source."""
    bought_deal_id: str
    deal_address: str
    deal_updated_at: Optional[datetime] = Field(None, description="The Bought deal's last change: a deal form loaded before it is stale.")
    is_linked: bool
    is_in_the_liquidity_timeline: bool
    liquidity_rows_are_out_of_date: bool = Field(..., description="A change to the deal still waits for its confirmation prompt.")
    # --- the rehab: the deal's own figures, editable from the card -------------------------------------------------
    actual_rehab_cost_dollars: float
    rehab_contingency_percent: float
    rehab_cost_dollars: float = Field(..., description="Actual rehab cost + contingency. Appliances are not part of it.")
    construction_budget_dollars: float
    original_steal_dollars: float = Field(..., description="Construction budget - rehab cost: positive = spread, negative = the rehab beyond the budget.")
    rehab_cushion_dollars: float = Field(..., description="The one deposit figure, stored on the Bought deal.")
    suggested_rehab_cushion_dollars: float
    rehab_beyond_the_construction_budget_dollars: float
    total_to_deposit_dollars: float = Field(..., description="Rehab cushion + rehab beyond the construction budget.")
    # --- the deal's dates and its rows on the timeline -------------------------------------------------------------
    purchase_closing_date: date
    rehab_completed_date: date
    rehab_completed_is_approved: bool
    refi_closing_date: date
    refi_closed_is_approved: bool
    timeline_rows: List[ConstructionAccountTimelineRowRes] = Field(
        default_factory=list, description="The deposit, return, top-up and appliances rows as the timeline has them.")
    appliances_dollars: float = Field(..., description="Not in this account: its own timeline row, paid from checking.")
    # --- only when linked ------------------------------------------------------------------------------------------
    mercury_workspace_label: Optional[str] = None
    construction_account: Optional[MercuryAccountNameRes] = None
    primary_checking_account: Optional[MercuryAccountNameRes] = None
    previous_construction_mercury_account_ids: List[str] = Field(default_factory=list)
    amounts_as_of: Optional[datetime] = Field(None, description="When the bank amounts were last read from Mercury; null = never.")
    mercury_is_unavailable: bool = False
    current_balance_dollars: Optional[float] = None
    available_balance_dollars: Optional[float] = None
    pending_money_in_dollars: Optional[float] = None
    pending_money_out_dollars: Optional[float] = None
    primary_checking_available_balance_dollars: Optional[float] = None
    loan_draws_pulled: Optional[ConstructionAccountSumBySourceRes] = None
    loan_draws_remaining_to_pull_dollars: Optional[float] = None
    percent_of_the_construction_budget_pulled: Optional[float] = None
    loan_draw_count: Optional[int] = None
    last_loan_draw: Optional[ConstructionAccountDatedAmountRes] = None
    rehab_payments_made: Optional[ConstructionAccountSumBySourceRes] = None
    unpaid_rehab_remaining_dollars: Optional[float] = None
    percent_of_the_rehab_paid: Optional[float] = None
    last_rehab_payment: Optional[ConstructionAccountDatedAmountRes] = None
    rehab_paid_by_payee: List[ConstructionAccountPayeeTotalRes] = Field(default_factory=list)
    own_money_transferred_into_the_account_dollars: Optional[float] = Field(None, description="Deposited so far.")
    own_money_transferred_out_of_the_account_dollars: Optional[float] = Field(None, description="Stolen so far.")
    own_money_still_in_the_account_dollars: Optional[float] = None
    spread_already_taken_dollars: Optional[float] = None
    remaining_deposit_dollars: Optional[float] = None
    minimum_balance_to_keep_in_construction_account_dollars: Optional[float] = None
    projected_return_at_rehab_end_dollars: Optional[float] = None
    own_money_back_at_rehab_end_dollars: Optional[float] = None
    spread_at_rehab_end_dollars: Optional[float] = None
    safe_to_steal_now_dollars: Optional[float] = None
    safe_to_steal_now_is_capped_by: Optional[SafeToStealCap] = None
    top_up_needed_dollars: Optional[float] = None
    loan_draws_pulled_before_construction_account_dollars: Optional[float] = None
    rehab_payments_made_before_construction_account_dollars: Optional[float] = None
    transactions_counted_count: Optional[int] = None
    transactions_ignored_count: Optional[int] = None
    transactions_recategorised_count: Optional[int] = None
    transactions_failed_or_cancelled_count: Optional[int] = None
    last_transaction_date: Optional[date] = None
    marked_ready_for_close_out_at: Optional[datetime] = None
    closed_out_at: Optional[datetime] = None
    manual_adjustments: List[ConstructionAccountManualAdjustmentRes] = Field(default_factory=list)
    transfers_made_in_the_app: List[ConstructionAccountTransferRes] = Field(default_factory=list)
    in_app_transfers_are_enabled: bool = False
    has_a_transfer_token: bool = False
    transfer_token_environment_variable_name: Optional[str] = None
    transfers_left_this_hour: Optional[int] = None
    maximum_single_transfer_dollars: Optional[float] = None
    needs_attention_because: List[Literal["deposit_due", "top_up_needed", "mercury_unavailable"]] = Field(default_factory=list)


class ConstructionAccountTotalsRes(BaseModel):
    """Across every linked account that is not closed out."""
    linked_account_count: int
    current_balance_dollars: float
    projected_return_at_rehab_end_dollars: float
    safe_to_steal_now_dollars: float
    remaining_deposit_dollars: float
    top_up_needed_dollars: float
    accounts_needing_attention_count: int


class ConstructionAccountListRes(BaseModel):
    totals: ConstructionAccountTotalsRes
    accounts: List[ConstructionAccountStatusRes]


class ConstructionAccountWriteRes(BaseModel):
    """The answer of every write. With `preview_only` nothing was saved: this is what confirming would do."""
    was_preview_only: bool
    status_before: ConstructionAccountStatusRes
    status_after: ConstructionAccountStatusRes
    changes_the_liquidity_timeline: bool
    liquidity_row_changes: Optional[DealCashRowChangesRes] = Field(
        None, description="The deal's rows before -> after; null for a deal that is not in the liquidity timeline.")
    row_descriptions_marked_done: List[str] = Field(default_factory=list)
    balance_left_in_the_account_dollars: Optional[float] = Field(
        None, description="Only when closing out: not $0 means money is still in the account (move it in Mercury, or Reopen).")


class ConstructionAccountTransferWriteRes(ConstructionAccountWriteRes):
    """A Deposit or a Steal: the write's answer, plus the transfer (null for a preview: nothing was asked of Mercury)."""
    transfer: Optional[ConstructionAccountTransferRes] = None


class ConstructionAccountSwitchPreviewRes(BaseModel):
    old_construction_account_balance_dollars: float
    old_account_must_be_emptied_first: bool
    loan_draws_pulled_before_construction_account_dollars: float = Field(..., description="The current baseline + the old account's categorised draws.")
    rehab_payments_made_before_construction_account_dollars: float = Field(..., description="The current baseline + the old account's categorised rehab payments.")


class ConstructionAccountTransactionRes(BaseModel):
    mercury_transaction_id: str
    transaction_date: Optional[date] = None
    counterparty_name: str
    signed_amount_dollars: float = Field(..., description="Positive = into the construction account.")
    bank_status: str
    is_pending: bool = False
    automatic_category: ConstructionAccountTransactionCategory
    ignored: bool
    category_override: Optional[ConstructionAccountTransactionCategory] = None
    note: Optional[str] = None
    effective_category: Optional[ConstructionAccountTransactionCategory] = Field(
        None, description="Null = counts for nothing: ignored by hand, or failed / cancelled at the bank.")


# --- Live Mercury -------------------------------------------------------------------------------------------------

class ConstructionAccountRefreshRes(BaseModel):
    refreshed_deal_count: int
    changed_row_count: int
    mercury_is_unavailable: bool
    next_mercury_read_not_before: Optional[datetime] = Field(None, description="Mercury is not read again before this (the shared pace, or a back-off).")
    cash_balance_changed: bool = Field(..., description="The cash on hand (the accounts counted as cash) changed in this refresh.")
    construction_accounts_changed: bool = Field(..., description="A linked construction account's numbers or rows changed in this refresh.")
    cash_balance_last_changed_at: Optional[datetime] = None
    construction_accounts_last_changed_at: Optional[datetime] = None
    bank_reported_row_changes: List[DealCashRowChangesRes] = Field(
        default_factory=list, description="Per deal, the rows this refresh changed because the bank reported something (already applied).")


class MercuryLastChangeRes(BaseModel):
    """From the database only, never a Mercury call: cheap enough to ask every few seconds."""
    last_changed_at: Optional[datetime] = None
    cash_balance_last_changed_at: Optional[datetime] = None
    construction_accounts_last_changed_at: Optional[datetime] = None
    last_instant_update_at: Optional[datetime] = Field(None, description="When a Mercury event last changed timeline rows.")
    bank_reported_row_changes_of_last_instant_update: List[DealCashRowChangesRes] = Field(
        default_factory=list, description="The rows that event changed, per deal: the 'Timeline updated from the bank' window.")


class MercuryWorkspaceConnectionRes(BaseModel):
    """One LLC's connection to Mercury. Names and times only: never a token, never a secret."""
    mercury_workspace_label: str
    has_read_token: bool
    has_transfer_token: bool
    read_token_environment_variable_name: str
    transfer_token_environment_variable_name: str
    instant_updates_are_on: bool
    last_valid_event_received_at: Optional[datetime] = None
    last_webhook_error_message: Optional[str] = None
    last_webhook_error_at: Optional[datetime] = None
    next_mercury_read_not_before: Optional[datetime] = None


class MercuryConnectionStatusRes(BaseModel):
    workspaces: List[MercuryWorkspaceConnectionRes]
    read_token_environment_variable_name_pattern: str
    transfer_token_environment_variable_name_pattern: str
