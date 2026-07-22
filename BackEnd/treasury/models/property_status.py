import uuid
from decimal import Decimal

from sqlalchemy import Column, String, Numeric, Boolean, ForeignKey, DateTime, func
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import relationship

from db import Base


def _new_id() -> str:
    return uuid.uuid4().hex


class PropertyStatus(Base):
    """Per-property treasury/reserve bookkeeping state.

    Every balance/settle/cap/debt column and target metric below is meant
    to be directly overridable by a human operator through the API and UI —
    the platform never enforces "computed" values over a manual edit — with
    ONE deliberate exception: `target_reserve_allocation` is now a *derived*
    value (`base_rent_target * precentage_of_rent_to_reserve / 100`) rather
    than a stored column, so the reserve target can never drift out of sync
    with the percentage the operator actually configured.
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
    # Explicit percentage input (e.g. 10.0 == 10% of rent swept to reserve).
    precentage_of_rent_to_reserve = Column(
        Numeric(6, 2), nullable=False, default=0, server_default="0"
    )

    # Renamed from `double_reserve_on_recovery`: when True, a recovery-rent
    # waterfall also chases *past* uncollected reserve targets, not just the
    # current month's target.
    chase_reserves = Column(
        Boolean, nullable=False, default=False, server_default="0"
    )

    @hybrid_property
    def target_reserve_allocation(self) -> Decimal:
        """Monthly reserve target in dollars, derived from the percentage.

        target_reserve_allocation = base_rent_target * (pct / 100)
        """
        rent = Decimal(self.base_rent_target or 0)
        pct = Decimal(self.precentage_of_rent_to_reserve or 0)
        return (rent * pct / Decimal("100")).quantize(Decimal("0.01"))

    @target_reserve_allocation.expression
    def target_reserve_allocation(cls):  # noqa: N805
        return cls.base_rent_target * cls.precentage_of_rent_to_reserve / 100

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
