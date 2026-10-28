"""Property inspections: the pre-purchase walkthrough checklist (tasks/todo/PropertyInspection.md).

An inspection is public: anyone with its id (a random uuid4) can read and
fill it in. It may be linked to at most one Bought Deal, which is either a
BRRRR or a FLIP deal, so the link is two nullable foreign keys of which at
most one is set. Deleting the deal clears the link and keeps the inspection.
"""

import uuid

from sqlalchemy import (
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    LargeBinary,
    String,
    UniqueConstraint,
    Uuid,
    func,
)

from db import Base

INSPECTION_STATUS_DRAFT = "draft"
INSPECTION_STATUS_COMPLETED = "completed"


class PropertyInspection(Base):
    __tablename__ = "property_inspections"
    __table_args__ = (
        CheckConstraint(
            "linked_bought_brrrr_deal_id IS NULL OR linked_bought_flip_deal_id IS NULL",
            name="property_inspections_linked_to_at_most_one_deal",
        ),
    )

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    property_address = Column(String, nullable=False)
    inspection_date = Column(Date, nullable=False)
    inspector_name = Column(String, nullable=True)
    inspection_status = Column(String, nullable=False, default=INSPECTION_STATUS_DRAFT)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    completion_override_reason = Column(String, nullable=True)
    linked_bought_brrrr_deal_id = Column(
        Uuid(as_uuid=True), ForeignKey("bought_brrrr_deals.id", ondelete="SET NULL"), nullable=True, index=True
    )
    linked_bought_flip_deal_id = Column(
        Uuid(as_uuid=True), ForeignKey("bought_flip_deals.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class PropertyInspectionItem(Base):
    """One checklist item's answers. A missing row means the item is not checked yet."""

    __tablename__ = "property_inspection_items"
    __table_args__ = (UniqueConstraint("inspection_id", "item_key", name="property_inspection_items_one_row_per_item"),)

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    inspection_id = Column(
        Uuid(as_uuid=True), ForeignKey("property_inspections.id", ondelete="CASCADE"), nullable=False, index=True
    )
    item_key = Column(String, nullable=False)
    item_status = Column(String, nullable=False, default="not_checked")
    item_notes = Column(String, nullable=True)
    item_field_values = Column(JSON, nullable=False, default=dict)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class PropertyInspectionPhoto(Base):
    """A photo of one item. The full image is in Google Drive; a small thumbnail is kept here."""

    __tablename__ = "property_inspection_photos"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    inspection_id = Column(
        Uuid(as_uuid=True), ForeignKey("property_inspections.id", ondelete="CASCADE"), nullable=False, index=True
    )
    item_key = Column(String, nullable=False)
    drive_file_id = Column(String, nullable=False)
    thumbnail_jpeg = Column(LargeBinary, nullable=False)
    full_image_byte_size = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


REPORT_DELIVERY_PENDING = "pending"
REPORT_DELIVERY_DELIVERED = "delivered"
REPORT_DELIVERY_FAILED = "failed"


class PropertyInspectionReport(Base):
    """The PDF report made each time an inspection is finished, and where it was sent.

    The PDF is kept as it was at that finish, so a retry sends exactly what was
    finished. E-mail and Drive are tracked separately: each is retried on its
    own until delivered or out of attempts (BL/inspection/common/inspection_report_delivery.py).
    """

    __tablename__ = "property_inspection_reports"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    inspection_id = Column(
        Uuid(as_uuid=True), ForeignKey("property_inspections.id", ondelete="CASCADE"), nullable=False, index=True
    )
    report_pdf = Column(LargeBinary, nullable=False)
    report_file_name = Column(String, nullable=False)
    email_delivery_status = Column(String, nullable=False, default=REPORT_DELIVERY_PENDING)
    email_attempt_count = Column(Integer, nullable=False, default=0)
    email_last_error_type = Column(String, nullable=True)
    emailed_at = Column(DateTime(timezone=True), nullable=True)
    drive_delivery_status = Column(String, nullable=False, default=REPORT_DELIVERY_PENDING)
    drive_attempt_count = Column(Integer, nullable=False, default=0)
    drive_last_error_type = Column(String, nullable=True)
    drive_file_id = Column(String, nullable=True)
    drive_folder_url = Column(String, nullable=True)
    saved_to_drive_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
