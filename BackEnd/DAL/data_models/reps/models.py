from sqlalchemy import Column, Integer, String, Boolean, DateTime, func, Uuid
import uuid

from db import Base


class RepsPerson(Base):
    """Audit-trail contact (contractor, agent, lender, etc.) referenced from REPS log entries."""

    __tablename__ = "reps_people"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    name = Column(String, nullable=False, unique=True, index=True)
    role = Column(String, nullable=True)
    notes = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class RepsProperty(Base):
    """Property/Prospect name referenced from REPS log entries.

    Bought-deal addresses are merged into the dropdown at read time;
    this table stores user-entered prospects (e.g., new addresses typed
    into the autocomplete that aren't bought yet).
    """

    __tablename__ = "reps_properties"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    name = Column(String, nullable=False, unique=True, index=True)
    is_prospect = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class RepsActivityCategory(Base):
    """User-managed activity-category dropdown for the REPS log form.

    Seeded with sensible defaults on first boot; users can add their own
    inline from the entry modal. Names are unique (case-insensitive at the
    application layer via crud_reps).
    """

    __tablename__ = "reps_activity_categories"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    name = Column(String, nullable=False, unique=True, index=True)
    sort_order = Column(Integer, nullable=False, default=0)
    is_default = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
