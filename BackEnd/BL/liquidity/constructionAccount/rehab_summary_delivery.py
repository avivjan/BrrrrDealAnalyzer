"""Delivers each rehab summary: e-mailed to the owner and saved to the owner's Google Drive
(tasks/todo/ConstructionAccountsCompactCardsAndRehabSummary.md).

Closing a construction account out (`mark_closed_out`) records a `LiquidityConstructionAccountRehabSummary` row with
the PDF and the CSV in the same transaction; the router then schedules `deliver_rehab_summaries_still_owed_after_commit`
as a background task, so closing out stays instant and a delivery failure never undoes it.

E-mail and Drive are delivered and tracked separately. A channel that failed is retried by
`retry_failed_rehab_summary_deliveries` (started from `main.py`, production only) every 30 minutes, at most 3 attempts
in all. Only the error's type name is ever stored: SMTP and Drive messages can name accounts.
"""

from __future__ import annotations

import logging
import os
import sys
import threading
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import or_
from sqlalchemy.orm import Session

from BL.liquidity.constructionAccount.rehab_summary_google_drive import (
    RehabSummaryDriveUploadFailed,
    rehab_summary_drive_folder_name,
    save_rehab_summary_file_to_drive as save_rehab_summary_file_to_drive_through_the_script,
)
from BL.liquidity.constructionAccount.rehab_summary_report import (
    RehabSummaryEmailAddressMissing,
    build_rehab_summary_content,
    build_rehab_summary_pdf,
    build_rehab_summary_transactions_csv,
    rehab_summary_email_address,
    rehab_summary_email_html,
    rehab_summary_email_subject,
    rehab_summary_email_text,
    rehab_summary_file_base_name,
    rehab_summary_sender_address,
    statistics_as_stored,
    statistics_from_stored,
)
from BL.memberLoan.common.member_loan_mail_transport import MemberLoanEmailAttachment, MemberLoanEmailNotSent, deliver_member_loan_email
from DAL.crud.liquidity_construction_account import get_rehab_summaries_of_deal
from DAL.data_models.liquidity.construction_account_models import (
    REHAB_SUMMARY_DELIVERY_DELIVERED, REHAB_SUMMARY_DELIVERY_FAILED, REHAB_SUMMARY_DELIVERY_PENDING, LiquidityConstructionAccountRehabSummary,
)
from ReqRes.common.liquidity_construction_account_schemas import (
    ConstructionAccountRehabSummaryRes, ConstructionAccountStatusRes, ConstructionAccountTransactionRes,
)
from db import SessionLocal

logger = logging.getLogger(__name__)

MAXIMUM_DELIVERY_ATTEMPTS_PER_CHANNEL = 3
MAXIMUM_REHAB_SUMMARIES_PER_DEAL_PER_DAY = 10
RETRY_INTERVAL_SECONDS = 30 * 60
STALE_PENDING_DELIVERY_SECONDS = 10 * 60
EMAIL_CHANNEL = "email"
DRIVE_CHANNEL = "drive"

# The two ways out, as names tests replace (tests/conftest.py never lets a test reach either).
send_rehab_summary_email = deliver_member_loan_email
save_rehab_summary_file_to_drive = save_rehab_summary_file_to_drive_through_the_script


def count_rehab_summaries_of_deal_today(db: Session, bought_brrr_deal_id) -> int:
    since = datetime.now(timezone.utc) - timedelta(days=1)
    return (db.query(LiquidityConstructionAccountRehabSummary)
            .filter(LiquidityConstructionAccountRehabSummary.bought_brrr_deal_id == bought_brrr_deal_id,
                    LiquidityConstructionAccountRehabSummary.created_at >= since).count())


def record_rehab_summary(db: Session, status: ConstructionAccountStatusRes, transactions: Optional[list[ConstructionAccountTransactionRes]],
                         closed_out_on: Optional[date]) -> LiquidityConstructionAccountRehabSummary:
    """Build the PDF and the CSV as things are now, and store them to be delivered. The caller commits."""
    content = build_rehab_summary_content(status, transactions, closed_out_on)
    summary = LiquidityConstructionAccountRehabSummary(
        id=uuid.uuid4(), bought_brrr_deal_id=uuid.UUID(str(status.bought_deal_id)), deal_address=status.deal_address[:300],
        summary_file_base_name=rehab_summary_file_base_name(content), summary_pdf_bytes=build_rehab_summary_pdf(content),
        summary_transactions_csv_text=build_rehab_summary_transactions_csv(content),
        summary_statistics=statistics_as_stored(content.statistics),
        email_delivery_status=REHAB_SUMMARY_DELIVERY_PENDING, email_delivery_attempt_count=0,
        drive_delivery_status=REHAB_SUMMARY_DELIVERY_PENDING, drive_delivery_attempt_count=0,
        created_at=datetime.now(timezone.utc),
    )
    db.add(summary)
    return summary


def overall_delivery_state(summary: LiquidityConstructionAccountRehabSummary) -> str:
    """delivered (both channels), sending, will_retry (a channel failed with attempts left), or failed (out of attempts)."""
    channel_states = [(summary.email_delivery_status, summary.email_delivery_attempt_count),
                      (summary.drive_delivery_status, summary.drive_delivery_attempt_count)]
    if all(status == REHAB_SUMMARY_DELIVERY_DELIVERED for status, _attempts in channel_states):
        return "delivered"
    if any(status == REHAB_SUMMARY_DELIVERY_FAILED and attempts >= MAXIMUM_DELIVERY_ATTEMPTS_PER_CHANNEL for status, attempts in channel_states):
        return "failed"
    if any(status == REHAB_SUMMARY_DELIVERY_FAILED for status, _attempts in channel_states):
        return "will_retry"
    return "sending"


def rehab_summary_res(summary: LiquidityConstructionAccountRehabSummary) -> ConstructionAccountRehabSummaryRes:
    return ConstructionAccountRehabSummaryRes(
        rehab_summary_id=str(summary.id), created_at=summary.created_at, overall_delivery_state=overall_delivery_state(summary),
        email_delivery_status=summary.email_delivery_status, email_last_error_type_name=summary.email_last_error_type_name,
        emailed_at=summary.emailed_at, drive_delivery_status=summary.drive_delivery_status,
        drive_last_error_type_name=summary.drive_last_error_type_name, saved_to_drive_at=summary.saved_to_drive_at,
        drive_folder_url=summary.drive_folder_url,
    )


def latest_rehab_summary_res(db: Session, bought_brrr_deal_id) -> Optional[ConstructionAccountRehabSummaryRes]:
    summaries = get_rehab_summaries_of_deal(db, bought_brrr_deal_id)
    return rehab_summary_res(summaries[0]) if summaries else None


def _deliver_to_drive(summary: LiquidityConstructionAccountRehabSummary) -> None:
    folder_name = rehab_summary_drive_folder_name(summary.deal_address, str(summary.bought_brrr_deal_id))
    if not summary.drive_pdf_file_id:
        summary.drive_pdf_file_id, folder_url = save_rehab_summary_file_to_drive(folder_name, f"{summary.summary_file_base_name}.pdf", summary.summary_pdf_bytes)
        summary.drive_folder_url = folder_url or summary.drive_folder_url
    if not summary.drive_csv_file_id:
        summary.drive_csv_file_id, folder_url = save_rehab_summary_file_to_drive(
            folder_name, f"{summary.summary_file_base_name} transactions.csv", summary.summary_transactions_csv_text.encode("utf-8"))
        summary.drive_folder_url = folder_url or summary.drive_folder_url


def _deliver_email(summary: LiquidityConstructionAccountRehabSummary) -> None:
    statistics = statistics_from_stored(summary.summary_statistics)
    send_rehab_summary_email(
        sender_address=rehab_summary_sender_address(),
        recipients=[rehab_summary_email_address()],
        subject=rehab_summary_email_subject(summary.deal_address),
        text_body=rehab_summary_email_text(summary.deal_address, statistics, summary.drive_folder_url),
        html_body=rehab_summary_email_html(summary.deal_address, statistics, summary.drive_folder_url),
        attachments=[
            MemberLoanEmailAttachment(filename=f"{summary.summary_file_base_name}.pdf", content=summary.summary_pdf_bytes),
            MemberLoanEmailAttachment(filename=f"{summary.summary_file_base_name} transactions.csv",
                                      content=summary.summary_transactions_csv_text.encode("utf-8"), mime_type="text", mime_subtype="csv"),
        ],
    )


def _channel_needs_delivery(summary: LiquidityConstructionAccountRehabSummary, channel: str, respect_attempt_limit: bool) -> bool:
    if getattr(summary, f"{channel}_delivery_status") == REHAB_SUMMARY_DELIVERY_DELIVERED:
        return False
    return not respect_attempt_limit or getattr(summary, f"{channel}_delivery_attempt_count") < MAXIMUM_DELIVERY_ATTEMPTS_PER_CHANNEL


def deliver_rehab_summary(rehab_summary_id: UUID, *, respect_attempt_limit: bool = True) -> dict:
    """Try every channel still owed. Drive goes first, so the e-mail can carry the folder link."""
    outcome: dict = {}
    with SessionLocal() as db:
        summary = db.get(LiquidityConstructionAccountRehabSummary, rehab_summary_id)
        if summary is None:
            return outcome
        for channel, deliver, failure_types in (
            (DRIVE_CHANNEL, lambda: _deliver_to_drive(summary), (RehabSummaryDriveUploadFailed,)),
            (EMAIL_CHANNEL, lambda: _deliver_email(summary), (MemberLoanEmailNotSent, RehabSummaryEmailAddressMissing)),
        ):
            if not _channel_needs_delivery(summary, channel, respect_attempt_limit):
                continue
            setattr(summary, f"{channel}_delivery_attempt_count", getattr(summary, f"{channel}_delivery_attempt_count") + 1)
            try:
                deliver()
            except failure_types as error:
                setattr(summary, f"{channel}_delivery_status", REHAB_SUMMARY_DELIVERY_FAILED)
                setattr(summary, f"{channel}_last_error_type_name", type(error).__name__)
                outcome[channel] = REHAB_SUMMARY_DELIVERY_FAILED
                logger.warning("rehab summary %s: %s delivery failed: %s", summary.id, channel, type(error).__name__)
            else:
                setattr(summary, f"{channel}_delivery_status", REHAB_SUMMARY_DELIVERY_DELIVERED)
                setattr(summary, f"{channel}_last_error_type_name", None)
                setattr(summary, "emailed_at" if channel == EMAIL_CHANNEL else "saved_to_drive_at", datetime.now(timezone.utc))
                outcome[channel] = REHAB_SUMMARY_DELIVERY_DELIVERED
            db.commit()
    return outcome


def deliver_rehab_summary_after_commit(rehab_summary_id: UUID) -> None:
    """The background task scheduled by a close-out or a Send again. Never raises."""
    try:
        deliver_rehab_summary(rehab_summary_id)
    except Exception:  # noqa: BLE001 -- a background task must not crash the worker
        logger.exception("rehab summary %s: delivery crashed", rehab_summary_id)


def retry_failed_rehab_summary_deliveries() -> int:
    """Retry every summary with a channel not yet delivered and attempts left. Returns how many were tried."""
    # A summary still "pending" after a while lost its background task (a restart): it is owed too.
    stale_pending_cutoff = datetime.now(timezone.utc) - timedelta(seconds=STALE_PENDING_DELIVERY_SECONDS)
    model = LiquidityConstructionAccountRehabSummary

    def channel_is_owed(status_column, attempt_count_column):
        return ((status_column != REHAB_SUMMARY_DELIVERY_DELIVERED)
                & (attempt_count_column < MAXIMUM_DELIVERY_ATTEMPTS_PER_CHANNEL)
                & ((status_column == REHAB_SUMMARY_DELIVERY_FAILED) | (model.created_at < stale_pending_cutoff)))

    with SessionLocal() as db:
        owed_rehab_summary_ids = [rehab_summary_id for (rehab_summary_id,) in db.query(model.id).filter(or_(
            channel_is_owed(model.email_delivery_status, model.email_delivery_attempt_count),
            channel_is_owed(model.drive_delivery_status, model.drive_delivery_attempt_count)))]
    for rehab_summary_id in owed_rehab_summary_ids:
        deliver_rehab_summary_after_commit(rehab_summary_id)
    return len(owed_rehab_summary_ids)


_retry_thread: Optional[threading.Thread] = None


def _retry_forever(stop: threading.Event) -> None:
    while not stop.wait(RETRY_INTERVAL_SECONDS):
        try:
            retry_failed_rehab_summary_deliveries()
        except Exception:  # noqa: BLE001 -- the loop must survive a bad round
            logger.exception("rehab summary retry round failed")


def start_rehab_summary_retry_schedule(is_production: bool) -> bool:
    """Start the retry loop once, in production only (tests and e2e never start it)."""
    global _retry_thread
    if not is_production or "pytest" in sys.modules or _retry_thread is not None:
        return False
    if (os.getenv("REHAB_SUMMARY_RETRY_SCHEDULE") or "on").strip().lower() == "off":
        return False
    _retry_thread = threading.Thread(target=_retry_forever, args=(threading.Event(),), name="rehab-summary-retry", daemon=True)
    _retry_thread.start()
    return True


def deliver_the_new_rehab_summaries_of_deal_after_commit(bought_deal_id: str) -> None:
    """After a close-out or a Send again commits: deliver the deal's summaries never tried yet. Never raises."""
    try:
        with SessionLocal() as db:
            never_tried_rehab_summary_ids = [summary.id for summary in get_rehab_summaries_of_deal(db, uuid.UUID(str(bought_deal_id)))
                                             if summary.email_delivery_attempt_count == 0 and summary.drive_delivery_attempt_count == 0]
    except Exception:  # noqa: BLE001 -- a background task must not crash the worker
        logger.exception("rehab summaries of deal %s: could not be read for delivery", bought_deal_id)
        return
    for rehab_summary_id in never_tried_rehab_summary_ids:
        deliver_rehab_summary_after_commit(rehab_summary_id)


def rehab_summary_of_deal(db: Session, bought_deal_id: str, rehab_summary_id: str) -> Optional[LiquidityConstructionAccountRehabSummary]:
    """One summary, only if it belongs to that deal (a summary id alone never reaches another deal's file)."""
    try:
        summary = db.get(LiquidityConstructionAccountRehabSummary, uuid.UUID(str(rehab_summary_id)))
    except ValueError:
        return None
    if summary is None or str(summary.bought_brrr_deal_id) != str(bought_deal_id):
        return None
    return summary
