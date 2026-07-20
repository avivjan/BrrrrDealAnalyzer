import uuid

from sqlalchemy import Column, String, Numeric, Boolean, ForeignKey, DateTime, func
from sqlalchemy.orm import relationship

from db import Base

VALID_SUB_BUCKETS = frozenset({"Tax", "Insurance", "General Reserve"})
VALID_TRANSACTION_TYPES = frozenset(
    {"Rent", "P&I", "Repair", "Emergency Advance", "Intercompany Loan"}
)


def _new_id() -> str:
    return uuid.uuid4().hex


class TransactionLedger(Base):
    """A single financial ledger line — real bank transaction or manual entry.

    Every mapped field the audit UI exposes is intentionally overridable
    end-to-end so a human can correct messy bank payloads without fighting
    the automation.
    """

    __tablename__ = "transaction_ledger"

    transaction_id = Column(String, primary_key=True, default=_new_id)
    property_id = Column(
        String,
        ForeignKey("property_status.property_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    amount = Column(Numeric(14, 2), nullable=False)
    description = Column(String, nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    is_real_bank_tx = Column(Boolean, nullable=False, default=False)
    sub_bucket_assignment = Column(String, nullable=True)
    transaction_type = Column(String, nullable=False)
    settlement_batch_id = Column(String, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    property = relationship("PropertyStatus", back_populates="transactions")
