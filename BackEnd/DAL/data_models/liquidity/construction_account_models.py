"""A rehab's own Mercury construction account, and the manual corrections on top of its bank feed
(tasks/todo/ConstructionAccountPerRehab.md).

The lender wires the draws into the construction account and the rehab payments leave from it, so neither is ever
a liquidity row. The bank feed is the default, never the only truth: the before-account baselines, the manual
payments and draws, and the per-transaction overrides below correct it by hand. No foreign keys to the deal table
(like the liquidity rows): deleting the Bought deal deletes its rows here in the same transaction.
"""

import uuid

from sqlalchemy import Boolean, Column, Date, DateTime, Integer, JSON, Numeric, String, Uuid, func

from db import Base

MANUAL_ADJUSTMENT_TYPE_MANUAL_PAYMENT = "manual_payment"
MANUAL_ADJUSTMENT_TYPE_MANUAL_DRAW = "manual_draw"
CONSTRUCTION_ACCOUNT_MANUAL_ADJUSTMENT_TYPES = (MANUAL_ADJUSTMENT_TYPE_MANUAL_PAYMENT, MANUAL_ADJUSTMENT_TYPE_MANUAL_DRAW)

TRANSACTION_CATEGORY_LOAN_DRAW = "loan_draw"
TRANSACTION_CATEGORY_REHAB_PAYMENT = "rehab_payment"
TRANSACTION_CATEGORY_OWN_MONEY = "own_money"
CONSTRUCTION_ACCOUNT_TRANSACTION_CATEGORIES = (
    TRANSACTION_CATEGORY_LOAN_DRAW, TRANSACTION_CATEGORY_REHAB_PAYMENT, TRANSACTION_CATEGORY_OWN_MONEY,
)


class LiquidityConstructionAccount(Base):
    """The construction account linked to one Bought BRRRR deal (one at a time; it can be switched mid-rehab)."""
    __tablename__ = "liquidity_construction_accounts"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    bought_brrr_deal_id = Column(Uuid(as_uuid=True), nullable=False, unique=True, index=True)
    # The Mercury workspace (LLC) both accounts live in: the label after MERCURY_API_TOKEN_.
    mercury_workspace_label = Column(String(80), nullable=False)
    construction_mercury_account_id = Column(String(80), nullable=False, unique=True)
    # Where a steal goes and where the deposit comes from: the same LLC's checking, counted as cash.
    primary_checking_mercury_account_id = Column(String(80), nullable=False)
    # The two accounts as Mercury named them when the link was last saved or refreshed, so the page can show them
    # without calling Mercury. Only the last four digits of a number are ever stored.
    construction_account_name = Column(String(200), nullable=False, default="", server_default="")
    construction_account_number_last_four = Column(String(4), nullable=False, default="", server_default="")
    primary_checking_account_name = Column(String(200), nullable=False, default="", server_default="")
    primary_checking_account_number_last_four = Column(String(4), nullable=False, default="", server_default="")
    # Accounts this rehab used before a switch, oldest first: [{"mercury_account_id": ..., "switched_away_at": ...}].
    previous_construction_mercury_account_ids = Column(JSON, nullable=False, default=list)
    # Rehab money that moved before this account existed (or through an earlier account): always editable.
    loan_draws_pulled_before_construction_account_dollars = Column(Numeric(16, 2), nullable=False, default=0, server_default="0")
    rehab_payments_made_before_construction_account_dollars = Column(Numeric(16, 2), nullable=False, default=0, server_default="0")
    # A float kept in the account (reimbursement draws): it lowers what is safe to steal.
    minimum_balance_to_keep_in_construction_account_dollars = Column(Numeric(16, 2), nullable=False, default=0, server_default="0")
    # What the bank feed said at the last refresh, after the overrides (NULL `bank_amounts_as_of` = never refreshed):
    # the projection is recomputed from these without Mercury on a deal save, a re-sync, or an outage.
    bank_current_balance_dollars = Column(Numeric(16, 2), nullable=False, default=0, server_default="0")
    bank_available_balance_dollars = Column(Numeric(16, 2), nullable=False, default=0, server_default="0")
    bank_loan_draws_dollars = Column(Numeric(16, 2), nullable=False, default=0, server_default="0")
    bank_rehab_payments_dollars = Column(Numeric(16, 2), nullable=False, default=0, server_default="0")
    bank_own_money_transferred_into_the_account_dollars = Column(Numeric(16, 2), nullable=False, default=0, server_default="0")
    bank_own_money_transferred_out_of_the_account_dollars = Column(Numeric(16, 2), nullable=False, default=0, server_default="0")
    bank_amounts_as_of = Column(DateTime(timezone=True), nullable=True)
    # For the page only, never part of the projection: pending money in / out, the checking's available balance, the
    # transaction counts, the last draw and the last payment, and the rehab paid per payee, as of that same refresh.
    bank_feed_details_as_of_last_refresh = Column(JSON, nullable=True)
    marked_ready_for_close_out_at = Column(DateTime(timezone=True), nullable=True)
    closed_out_at = Column(DateTime(timezone=True), nullable=True)
    linked_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class LiquidityConstructionAccountManualAdjustment(Base):
    """Rehab money that never touched the construction account: a contractor paid from another account, a credit-card
    material run, cash (`manual_payment`), or a draw the lender wired elsewhere (`manual_draw`)."""
    __tablename__ = "liquidity_construction_account_manual_adjustments"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    bought_brrr_deal_id = Column(Uuid(as_uuid=True), nullable=False, index=True)
    adjustment_type = Column(String(20), nullable=False)   # one of CONSTRUCTION_ACCOUNT_MANUAL_ADJUSTMENT_TYPES
    amount_dollars = Column(Numeric(16, 2), nullable=False)   # always positive
    note = Column(String(500), nullable=True)
    date = Column(Date, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class LiquidityConstructionAccountTransactionOverride(Base):
    """A hand correction of one bank transaction of a construction account: ignore it, or put it in another category."""
    __tablename__ = "liquidity_construction_account_transaction_overrides"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    mercury_transaction_id = Column(String(80), nullable=False, unique=True, index=True)
    bought_brrr_deal_id = Column(Uuid(as_uuid=True), nullable=False, index=True)
    ignored = Column(Boolean, nullable=False, default=False, server_default="false")
    category_override = Column(String(20), nullable=True)   # one of CONSTRUCTION_ACCOUNT_TRANSACTION_CATEGORIES, or NULL
    note = Column(String(500), nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


TRANSFER_DIRECTION_DEPOSIT_INTO_CONSTRUCTION_ACCOUNT = "deposit_into_construction_account"
TRANSFER_DIRECTION_STEAL_TO_PRIMARY_CHECKING = "steal_to_primary_checking"
CONSTRUCTION_ACCOUNT_TRANSFER_DIRECTIONS = (TRANSFER_DIRECTION_DEPOSIT_INTO_CONSTRUCTION_ACCOUNT, TRANSFER_DIRECTION_STEAL_TO_PRIMARY_CHECKING)

# What became of a transfer the app asked Mercury for.
TRANSFER_OUTCOME_BEING_SENT = "being_sent"                      # the row is saved, the request is on its way
TRANSFER_OUTCOME_ACCEPTED_BY_MERCURY = "accepted_by_mercury"    # counts at once (until the bank feed shows it)
TRANSFER_OUTCOME_REFUSED_BY_MERCURY = "refused_by_mercury"      # nothing was sent
TRANSFER_OUTCOME_MERCURY_DID_NOT_ANSWER = "mercury_did_not_answer"   # maybe sent: check Mercury before trying again
TRANSFER_OUTCOME_FAILED_OR_CANCELLED_AT_MERCURY = "failed_or_cancelled_at_mercury"   # the bank feed says so
TRANSFER_OUTCOMES_THAT_COUNT = (TRANSFER_OUTCOME_ACCEPTED_BY_MERCURY,)


class LiquidityConstructionAccountTransfer(Base):
    """A Deposit or a Steal the app asked Mercury to make. Kept after an unlink or the deal's deletion: it is the record
    of real money moved. It counts toward its account's own money from the moment Mercury accepts it, until the bank
    feed shows it (then the feed counts it, once)."""
    __tablename__ = "liquidity_construction_account_transfers"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    bought_brrr_deal_id = Column(Uuid(as_uuid=True), nullable=False, index=True)
    construction_mercury_account_id = Column(String(80), nullable=False, index=True)
    source_mercury_account_id = Column(String(80), nullable=False)
    destination_mercury_account_id = Column(String(80), nullable=False)
    mercury_workspace_label = Column(String(80), nullable=False)
    transfer_direction = Column(String(40), nullable=False)   # one of CONSTRUCTION_ACCOUNT_TRANSFER_DIRECTIONS
    amount_dollars = Column(Numeric(16, 2), nullable=False)   # always positive
    # One per open transfer window in the browser: the same key never makes a second transfer.
    idempotency_key = Column(String(80), nullable=False, unique=True)
    transfer_outcome = Column(String(40), nullable=False)
    mercury_transfer_id = Column(String(80), nullable=True)
    mercury_transfer_status = Column(String(20), nullable=True)   # pending / sent / cancelled / failed / unknown
    # Mercury refused it: the HTTP status it answered (401/403 the token, 400/422 the request, 429 slow down).
    mercury_refusal_http_status = Column(Integer, nullable=True)
    requested_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)
    requested_by_user_id = Column(Uuid(as_uuid=True), nullable=True)
    # The bank transaction this transfer was matched to, once the feed shows it.
    mercury_transaction_id_in_the_bank_feed = Column(String(80), nullable=True, unique=True)
    seen_in_the_bank_feed_at = Column(DateTime(timezone=True), nullable=True)
