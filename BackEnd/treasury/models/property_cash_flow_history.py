import uuid

from sqlalchemy import Column, String, Numeric, ForeignKey, DateTime, func
from sqlalchemy.orm import relationship

from db import Base


def _new_id() -> str:
    return uuid.uuid4().hex


class PropertyCashFlowHistory(Base):
    """A single monthly cash-flow snapshot for a property.

    `monthly_cash_flow` and `cumulative_cash_flow` are stored, editable
    facts, not derived values recomputed on read — a human can correct a
    historical snapshot without the platform silently recalculating it.
    """

    __tablename__ = "property_cash_flow_history"

    history_id = Column(String, primary_key=True, default=_new_id)
    property_id = Column(
        String,
        ForeignKey("property_status.property_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    month_year = Column(String, nullable=False)
    monthly_cash_flow = Column(Numeric(14, 2), nullable=False, default=0)
    cumulative_cash_flow = Column(Numeric(14, 2), nullable=False, default=0)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    property = relationship("PropertyStatus", back_populates="cash_flow_history")
