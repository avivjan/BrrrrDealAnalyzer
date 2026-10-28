"""Delivers the report of each finished inspection: e-mailed, and saved to Drive.

Finishing an inspection (`complete_public_inspection`) records a
`PropertyInspectionReport` row holding the PDF, in the same transaction, and
schedules `deliver_inspection_report_after_commit` as a background task, so
finishing stays instant and a delivery failure never undoes the finish.

E-mail and Drive are delivered and tracked separately. A channel that failed
is retried by `retry_failed_inspection_report_deliveries` (started from
`main.py`, production only) every 30 minutes, at most 3 attempts in all. Only
the error's type name is ever stored: SMTP and Drive messages can name accounts.
"""

from __future__ import annotations

import logging
import os
import sys
import threading
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import or_
from sqlalchemy.orm import Session

from BL.inspection.common.inspection_photo_google_drive import (
    InspectionPhotoStorageUnavailable,
    inspection_drive_folder_name,
    save_inspection_report_to_drive,
)
from BL.inspection.common.inspection_report import (
    build_inspection_report_content,
    build_inspection_report_pdf,
    inspection_report_email_address,
    inspection_report_email_html,
    inspection_report_email_subject,
    inspection_report_email_text,
    inspection_report_file_name,
    inspection_report_sender_address,
)
from BL.memberLoan.common.member_loan_mail_transport import MemberLoanEmailAttachment, MemberLoanEmailNotSent, deliver_member_loan_email
from DAL.crud.inspection import get_inspection_by_id, get_items_of_inspection, get_photos_of_inspection
from DAL.data_models import PropertyInspection, PropertyInspectionReport
from DAL.data_models.inspection.models import REPORT_DELIVERY_DELIVERED, REPORT_DELIVERY_FAILED
from db import SessionLocal

logger = logging.getLogger(__name__)

MAXIMUM_DELIVERY_ATTEMPTS_PER_CHANNEL = 3
MAXIMUM_REPORTS_PER_INSPECTION_PER_DAY = 10
RETRY_INTERVAL_SECONDS = 30 * 60
STALE_PENDING_DELIVERY_SECONDS = 10 * 60

# The two ways out, as names tests replace (tests/conftest.py never lets a test reach either).
send_inspection_report_email = deliver_member_loan_email
save_inspection_report_pdf_to_drive = save_inspection_report_to_drive

EMAIL_CHANNEL = "email"
DRIVE_CHANNEL = "drive"


def count_reports_of_inspection_today(db: Session, inspection_id: UUID) -> int:
    since = datetime.now(timezone.utc) - timedelta(days=1)
    return (
        db.query(PropertyInspectionReport)
        .filter(PropertyInspectionReport.inspection_id == inspection_id, PropertyInspectionReport.created_at >= since)
        .count()
    )


def record_inspection_report(db: Session, inspection: PropertyInspection) -> PropertyInspectionReport:
    """Builds the PDF of the inspection as finished now. The caller commits."""

    content = build_inspection_report_content(inspection, get_items_of_inspection(db, inspection.id), get_photos_of_inspection(db, inspection.id))
    report = PropertyInspectionReport(
        inspection_id=inspection.id,
        report_pdf=build_inspection_report_pdf(content),
        report_file_name=inspection_report_file_name(content),
    )
    db.add(report)
    return report


def latest_report_delivery_status(db: Session, inspection_id: UUID) -> Optional[str]:
    """The public, address-free view of the last report: none, sending, delivered or will_retry."""

    report = (
        db.query(PropertyInspectionReport)
        .filter(PropertyInspectionReport.inspection_id == inspection_id)
        .order_by(PropertyInspectionReport.created_at.desc())
        .first()
    )
    if report is None:
        return None
    statuses = {report.email_delivery_status, report.drive_delivery_status}
    if statuses == {REPORT_DELIVERY_DELIVERED}:
        return "delivered"
    if REPORT_DELIVERY_FAILED in statuses:
        return "will_retry"
    return "sending"


def _deliver_email(report: PropertyInspectionReport, inspection: PropertyInspection, content, drive_folder_url: Optional[str]) -> None:
    send_inspection_report_email(
        sender_address=inspection_report_sender_address(),
        recipients=[inspection_report_email_address()],
        subject=inspection_report_email_subject(content),
        text_body=inspection_report_email_text(content, drive_folder_url),
        html_body=inspection_report_email_html(content, drive_folder_url),
        attachments=[MemberLoanEmailAttachment(filename=report.report_file_name, content=report.report_pdf)],
    )


def _deliver_to_drive(report: PropertyInspectionReport, inspection: PropertyInspection) -> None:
    folder_name = inspection_drive_folder_name(inspection.inspection_date.isoformat(), inspection.property_address, str(inspection.id))
    report.drive_file_id, report.drive_folder_url = save_inspection_report_pdf_to_drive(
        folder_name, report.report_file_name, report.report_pdf
    )


def _channel_needs_delivery(report: PropertyInspectionReport, channel: str, respect_attempt_limit: bool) -> bool:
    status = getattr(report, f"{channel}_delivery_status")
    attempts = getattr(report, f"{channel}_attempt_count")
    if status == REPORT_DELIVERY_DELIVERED:
        return False
    return not respect_attempt_limit or attempts < MAXIMUM_DELIVERY_ATTEMPTS_PER_CHANNEL


def deliver_inspection_report(report_id: UUID, *, respect_attempt_limit: bool = True) -> dict:
    """Tries every channel still owed. Drive goes first, so the e-mail can carry the folder link."""

    outcome: dict = {}
    with SessionLocal() as db:
        report = db.get(PropertyInspectionReport, report_id)
        inspection = get_inspection_by_id(db, report.inspection_id) if report else None
        if report is None or inspection is None:
            return outcome
        content = build_inspection_report_content(inspection, get_items_of_inspection(db, inspection.id), get_photos_of_inspection(db, inspection.id))
        content.completed_at = content.completed_at or report.created_at
        for channel, deliver, failure_types in (
            (DRIVE_CHANNEL, lambda: _deliver_to_drive(report, inspection), (InspectionPhotoStorageUnavailable,)),
            (EMAIL_CHANNEL, lambda: _deliver_email(report, inspection, content, report.drive_folder_url), (MemberLoanEmailNotSent,)),
        ):
            if not _channel_needs_delivery(report, channel, respect_attempt_limit):
                continue
            setattr(report, f"{channel}_attempt_count", getattr(report, f"{channel}_attempt_count") + 1)
            try:
                deliver()
            except failure_types as error:
                setattr(report, f"{channel}_delivery_status", REPORT_DELIVERY_FAILED)
                setattr(report, f"{channel}_last_error_type", type(error).__name__)
                outcome[channel] = REPORT_DELIVERY_FAILED
                logger.warning("inspection report %s: %s delivery failed: %s", report.id, channel, type(error).__name__)
            else:
                setattr(report, f"{channel}_delivery_status", REPORT_DELIVERY_DELIVERED)
                setattr(report, f"{channel}_last_error_type", None)
                setattr(report, "emailed_at" if channel == EMAIL_CHANNEL else "saved_to_drive_at", datetime.now(timezone.utc))
                outcome[channel] = REPORT_DELIVERY_DELIVERED
            db.commit()
    return outcome


def deliver_inspection_report_after_commit(report_id: UUID) -> None:
    """The background task scheduled by finishing an inspection. Never raises."""

    try:
        deliver_inspection_report(report_id)
    except Exception:  # noqa: BLE001 -- a background task must not crash the worker
        logger.exception("inspection report %s: delivery crashed", report_id)


def retry_failed_inspection_report_deliveries() -> int:
    """Retries every report with a channel not yet delivered and attempts left. Returns how many were tried."""

    # A report still "pending" after a while lost its background task (a restart): it is owed too.
    stale_pending_cutoff = datetime.now(timezone.utc) - timedelta(seconds=STALE_PENDING_DELIVERY_SECONDS)

    def channel_is_owed(status_column, attempt_count_column):
        return (
            (status_column != REPORT_DELIVERY_DELIVERED)
            & (attempt_count_column < MAXIMUM_DELIVERY_ATTEMPTS_PER_CHANNEL)
            & ((status_column == REPORT_DELIVERY_FAILED) | (PropertyInspectionReport.created_at < stale_pending_cutoff))
        )

    with SessionLocal() as db:
        owed_report_ids = [
            report_id
            for (report_id,) in db.query(PropertyInspectionReport.id).filter(
                or_(
                    channel_is_owed(PropertyInspectionReport.email_delivery_status, PropertyInspectionReport.email_attempt_count),
                    channel_is_owed(PropertyInspectionReport.drive_delivery_status, PropertyInspectionReport.drive_attempt_count),
                )
            )
        ]
    for report_id in owed_report_ids:
        deliver_inspection_report_after_commit(report_id)
    return len(owed_report_ids)


_retry_thread: Optional[threading.Thread] = None


def _retry_forever(stop: threading.Event) -> None:
    while not stop.wait(RETRY_INTERVAL_SECONDS):
        try:
            retry_failed_inspection_report_deliveries()
        except Exception:  # noqa: BLE001 -- the loop must survive a bad round
            logger.exception("inspection report retry round failed")


def start_inspection_report_retry_schedule(is_production: bool) -> bool:
    """Start the retry loop once, in production only (tests and e2e never start it)."""

    global _retry_thread
    if not is_production or "pytest" in sys.modules or _retry_thread is not None:
        return False
    if (os.getenv("INSPECTION_REPORT_RETRY_SCHEDULE") or "on").strip().lower() == "off":
        return False
    _retry_thread = threading.Thread(target=_retry_forever, args=(threading.Event(),), name="inspection-report-retry", daemon=True)
    _retry_thread.start()
    return True
