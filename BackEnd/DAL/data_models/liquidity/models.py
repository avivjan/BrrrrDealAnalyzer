from sqlalchemy import Column, Integer, String, DateTime, Date, func, Numeric, Uuid
import uuid

from db import Base


class LiquidityTransaction(Base):
    """A single cash flow event on the liquidity timeline.
    amount_k is signed: positive = inflow, negative = outflow.
    All amounts are in thousands of dollars ($k).
    """
    __tablename__ = "liquidity_transactions"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    effective_date = Column(Date, nullable=False, index=True)
    description = Column(String, nullable=False)
    amount_k = Column(Numeric(14, 4), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class LiquidityRecurringTransaction(Base):
    """A repeating cash-flow rule (e.g. monthly hard-money interest).

    A rule is expanded into virtual `LiquidityTransaction`-shaped events
    on the frontend timeline at read time, so editing a rule retroactively
    fixes every projected occurrence without rewriting per-row history.

    Sign convention matches `LiquidityTransaction.amount_k`: positive ==
    inflow, negative == outflow. All amounts in thousands of dollars ($k).
    """

    __tablename__ = "liquidity_recurring_transactions"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    description = Column(String, nullable=False)
    amount_k = Column(Numeric(14, 4), nullable=False)
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
    opening_balance_k: balance at start-of-day on opening_balance_date, in $k.
    reserve_k: soft-warning threshold, in $k.
    """
    __tablename__ = "liquidity_settings"

    id = Column(Integer, primary_key=True, default=1)
    opening_balance_k = Column(Numeric(14, 4), nullable=False, default=0)
    opening_balance_date = Column(Date, nullable=False)
    reserve_k = Column(Numeric(14, 4), nullable=False, default=5)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
