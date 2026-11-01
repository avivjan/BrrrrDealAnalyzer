from sqlalchemy import Boolean, Column, Integer, String, DateTime, Date, func, Numeric, Uuid, JSON
import uuid

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
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
