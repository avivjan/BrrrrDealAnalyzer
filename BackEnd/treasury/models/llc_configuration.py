import uuid

from sqlalchemy import Column, String, Numeric, DateTime, func
from sqlalchemy.orm import relationship

from db import Base


def _new_id() -> str:
    return uuid.uuid4().hex


class LLCConfiguration(Base):
    """One row per holding LLC.

    `checking_redline_buffer` is the minimum balance the operating checking
    account must keep on hand before the platform treats the LLC as
    under-funded. It is a pure user-editable control value — no automated
    process may silently change it.
    """

    __tablename__ = "llc_configuration"

    llc_id = Column(String, primary_key=True, default=_new_id)
    llc_name = Column(String, nullable=False)
    checking_redline_buffer = Column(
        Numeric(14, 2), nullable=False, default=1000.00, server_default="1000.00"
    )

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    properties = relationship(
        "PropertyStatus",
        back_populates="llc",
        cascade="all, delete-orphan",
    )
