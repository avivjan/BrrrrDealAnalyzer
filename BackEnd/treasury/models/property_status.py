import uuid

from sqlalchemy import Column, String, Numeric, Boolean, ForeignKey, DateTime, func
from sqlalchemy.orm import relationship

from db import Base


def _new_id() -> str:
    return uuid.uuid4().hex


class PropertyStatus(Base):
    """Per-property treasury/reserve bookkeeping state.

    Every balance/settle/cap/debt column, target metric, and control flag
    below is meant to be directly overridable by a human operator through
    the API and UI — the platform never enforces "computed" values over a
    manual edit.
    """

    __tablename__ = "property_status"

    property_id = Column(String, primary_key=True, default=_new_id)
    llc_id = Column(
        String,
        ForeignKey("llc_configuration.llc_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    property_name = Column(String, nullable=False, default="", server_default="")

    tax_bucket_balance = Column(Numeric(14, 2), nullable=False, default=0)
    tax_to_settle = Column(Numeric(14, 2), nullable=False, default=0)
    reserve_bucket_balance = Column(Numeric(14, 2), nullable=False, default=0)
    reserve_to_settle = Column(Numeric(14, 2), nullable=False, default=0)
    reserve_bucket_cap = Column(Numeric(14, 2), nullable=False, default=0)
    reserve_debt = Column(Numeric(14, 2), nullable=False, default=0)

    base_rent_target = Column(Numeric(14, 2), nullable=False, default=0)
    target_tax_allocation = Column(Numeric(14, 2), nullable=False, default=0)
    target_reserve_allocation = Column(Numeric(14, 2), nullable=False, default=0)

    double_reserve_on_recovery = Column(Boolean, nullable=False, default=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    llc = relationship("LLCConfiguration", back_populates="properties")
    cash_flow_history = relationship(
        "PropertyCashFlowHistory",
        back_populates="property",
        cascade="all, delete-orphan",
    )
    transactions = relationship(
        "TransactionLedger",
        back_populates="property",
    )
