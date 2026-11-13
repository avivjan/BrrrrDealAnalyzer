from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, DateTime, Date, func, Numeric, Uuid, JSON, UniqueConstraint
import uuid

from sqlalchemy.orm import relationship

from db import Base


class LiquidityTransaction(Base):
    """A single cash flow event on the liquidity timeline.
    amount_dollars is signed: positive = inflow, negative = outflow, in exact dollars.

    A row leaves the timeline only when it is marked done (`done_at`), never because its date
    passed: an open row dated before today is overdue (money out counts on today, money in is
    expected but not counted until it is re-dated or marked done).
    """
    __tablename__ = "liquidity_transactions"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    effective_date = Column(Date, nullable=False, index=True)
    description = Column(String, nullable=False)
    amount_dollars = Column(Numeric(16, 2), nullable=False)
    # Set when the money really moved (or a hold is released); NULL = still open.
    done_at = Column(DateTime(timezone=True), nullable=True)
    # The date the row was first created or imported with, for the "moved from ..." text.
    originally_planned_date = Column(Date, nullable=True)
    # The user changed the date / the amount by hand; a re-sync from a deal keeps that field.
    user_overrode_date = Column(Boolean, nullable=False, default=False, server_default="false")
    user_overrode_amount = Column(Boolean, nullable=False, default=False, server_default="false")
    # A row imported from a deal's Cash Needed schedule: which deal (the board says which table), and its
    # identity there (item_key + occurrence number, never the date). NULL on a manual transaction.
    source_deal_board = Column(String(20), nullable=True)
    source_deal_id = Column(Uuid(as_uuid=True), nullable=True, index=True)
    source_item_key = Column(String(80), nullable=True)
    source_occurrence_number = Column(Integer, nullable=True)
    sequence_within_day = Column(Integer, nullable=True)
    # Added while the deal's refi was late (planned date passed, not approved): a real month of carrying costs.
    created_because_refi_is_late = Column(Boolean, nullable=False, default=False, server_default="false")
    # The deal no longer has this row, but it carries an override, so it stayed.
    no_longer_in_the_deal = Column(Boolean, nullable=False, default=False, server_default="false")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class LiquidityRecurringTransaction(Base):
    """A repeating cash-flow rule (e.g. monthly hard-money interest).

    A rule is expanded into virtual `LiquidityTransaction`-shaped events
    on the frontend timeline at read time, so editing a rule retroactively
    fixes every projected occurrence without rewriting per-row history.

    Sign convention matches `LiquidityTransaction.amount_dollars`: positive ==
    inflow, negative == outflow. All amounts in exact dollars.
    """

    __tablename__ = "liquidity_recurring_transactions"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    description = Column(String, nullable=False)
    amount_dollars = Column(Numeric(16, 2), nullable=False)
    # First occurrence date. All later occurrences are derived from this
    # anchor (so changing it shifts the entire series).
    start_date = Column(Date, nullable=False, index=True)
    # Optional hard stop. If both `end_date` and `occurrences` are NULL the
    # series runs forever; the frontend caps it at the visible timeline.
    end_date = Column(Date, nullable=True)
    # Optional max number of events (1-based count). Useful for "interest
    # for the next 12 months" style series. Mutually compatible with
    # end_date; whichever cap fires first wins.
    occurrences = Column(Integer, nullable=True)
    frequency = Column(String, nullable=False)  # one of LIQUIDITY_RECURRING_FREQUENCIES
    # "Every N units" multiplier on top of `frequency`. Defaults to 1.
    interval = Column(Integer, nullable=False, default=1, server_default="1")
    # An occurrence before this date is history (already in the bank balance), never overdue: the day the rule was
    # added (existing rules: the migration date). NULL reads as the rule's start date.
    occurrences_can_be_overdue_from = Column(Date, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    occurrence_states = relationship("LiquidityRecurringOccurrenceState", cascade="all, delete-orphan", passive_deletes=True,
                                     order_by="LiquidityRecurringOccurrenceState.scheduled_date")


class LiquidityRecurringOccurrenceState(Base):
    """One occurrence of a recurring rule, marked done and/or moved to another date (it is open on its own date
    otherwise). Keyed by the date the rule gives the occurrence, so editing the rule's amount or description keeps
    the state; a schedule change leaves states that no longer match an occurrence, and they are ignored."""

    __tablename__ = "liquidity_recurring_occurrence_states"
    __table_args__ = (UniqueConstraint("recurring_rule_id", "scheduled_date", name="uq_recurring_occurrence_state"),)

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    recurring_rule_id = Column(Uuid(as_uuid=True), ForeignKey("liquidity_recurring_transactions.id", ondelete="CASCADE"),
                               nullable=False, index=True)
    scheduled_date = Column(Date, nullable=False)
    done_at = Column(DateTime(timezone=True), nullable=True)
    moved_to_date = Column(Date, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class LiquiditySettings(Base):
    """Singleton row (id=1) holding the opening balance anchor and user prefs.
    opening_balance_dollars: balance at start-of-day on opening_balance_date, in dollars.
    reserve_dollars: soft-warning threshold, in dollars.
    mercury_account_ids_counted_as_cash: the Mercury account ids whose balance is cash on hand (the
    operating accounts); NULL = every active account. The tax bucket and the HYSA are left out so
    the deposits into them read as money out.
    """
    __tablename__ = "liquidity_settings"

    id = Column(Integer, primary_key=True, default=1)
    opening_balance_dollars = Column(Numeric(16, 2), nullable=False, default=0)
    opening_balance_date = Column(Date, nullable=False)
    reserve_dollars = Column(Numeric(16, 2), nullable=False, default=5000)
    mercury_account_ids_counted_as_cash = Column(JSON, nullable=True)
    # The owner's time zone: "today" for the backend (the late-refi rows on an MCP read). The browser sends its own date.
    timezone_name = Column(String(64), nullable=False, default="America/New_York", server_default="America/New_York")
    # Construction accounts (tasks/todo/ConstructionAccountPerRehab.md): every setting lives here, edited in the UI.
    # How often an open page re-reads Mercury, and whether it does so when its window regains focus.
    construction_account_refresh_interval_seconds = Column(Integer, nullable=False, default=30, server_default="30")
    construction_account_refresh_when_window_regains_focus = Column(Boolean, nullable=False, default=True, server_default="true")
    # The kill switch and the limits of the in-app Deposit and Steal transfers.
    construction_account_in_app_transfers_enabled = Column(Boolean, nullable=False, default=True, server_default="true")
    construction_account_transfers_per_hour_limit = Column(Integer, nullable=False, default=5, server_default="5")
    construction_account_maximum_single_transfer_dollars = Column(Numeric(16, 2), nullable=False, default=100000, server_default="100000")
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
