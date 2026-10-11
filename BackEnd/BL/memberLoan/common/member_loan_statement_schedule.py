"""Sends the monthly Member Loan statement from inside the web service.

No separate cron job is needed: in production a background thread checks every
30 minutes. From 06:00 in New York on the 1st, it sends the statement for the
month that just ended. It reuses `send_member_loan_statement`, so the database
still guarantees a month is never sent twice, even with several instances.

  - Dry-run mode (MEMBER_LOAN_EMAIL_DRY_RUN not `false`): the thread does nothing.
    A manual dry run is `python manage.py send-member-loan-statement --dry-run`.
  - A failed send (SMTP error) is retried on later checks, at most
    AUTOMATIC_RETRIES_AFTER_A_FAILURE times. A send interrupted mid-way
    (`sending`) is never repeated automatically.
  - Turn the thread off with MEMBER_LOAN_STATEMENT_SCHEDULE=off.
"""

from __future__ import annotations

import logging
import os
import sys
import threading
from datetime import datetime
from typing import Optional

from BL.memberLoan.common import member_loan_settings
from BL.memberLoan.common.member_loan_engine import first_day_of_previous_month
from BL.memberLoan.common.member_loan_settings import LOAN_TIME_ZONE, MemberLoanMisconfigured
from BL.memberLoan.common.member_loan_statement_sender import MemberLoanStatementSendResult, send_member_loan_statement
from DAL.crud import member_loan as member_loan_crud
from db import SessionLocal

logger = logging.getLogger(__name__)

CHECK_INTERVAL_SECONDS = 30 * 60
EARLIEST_SEND_HOUR_IN_NEW_YORK_ON_THE_1ST = 6
AUTOMATIC_RETRIES_AFTER_A_FAILURE = 3

_schedule_thread: Optional[threading.Thread] = None


def run_member_loan_statement_schedule_check() -> Optional[MemberLoanStatementSendResult]:
    """One check. Returns what happened, or None when there was nothing to do. Never raises."""

    try:
        settings = member_loan_settings.load_member_loan_settings()
    except MemberLoanMisconfigured:
        return None
    if settings.statement_email_dry_run:
        return None
    now_in_new_york: datetime = member_loan_settings.utc_now().astimezone(LOAN_TIME_ZONE)
    if now_in_new_york.day == 1 and now_in_new_york.hour < EARLIEST_SEND_HOUR_IN_NEW_YORK_ON_THE_1ST:
        return None
    month = first_day_of_previous_month(now_in_new_york.date())
    try:
        with SessionLocal() as db:
            real_sends = [s for s in member_loan_crud.list_member_loan_statement_sends(db, month) if not s.is_dry_run]
            if any(s.status in ("sent", "sending") for s in real_sends):
                return None
            failed_attempts = sum(1 for s in real_sends if s.status == "failed")
            if failed_attempts > AUTOMATIC_RETRIES_AFTER_A_FAILURE:
                return None
            result = send_member_loan_statement(db, statement_month=month, retry_failed=failed_attempts > 0)
    except Exception:  # noqa: BLE001 -- a scheduling error must never take the web service down
        logger.exception("member loan: the monthly statement check failed")
        return None
    if result.outcome in ("sent", "failed"):
        logger.info("member loan statement %s: %s", month.strftime("%Y-%m"), result.outcome)
    return result


FIRST_CHECK_AFTER_STARTUP_SECONDS = 60


def _check_forever(stop: threading.Event) -> None:
    if stop.wait(timeout=FIRST_CHECK_AFTER_STARTUP_SECONDS):
        return
    while True:
        run_member_loan_statement_schedule_check()
        if stop.wait(timeout=CHECK_INTERVAL_SECONDS):
            return


def start_member_loan_statement_schedule(is_production: bool) -> bool:
    """Start the background check once, in production only (tests and e2e never start it)."""

    global _schedule_thread
    if not is_production or (os.getenv("MEMBER_LOAN_STATEMENT_SCHEDULE") or "on").strip().lower() == "off":
        return False
    if "pytest" in sys.modules:
        # A Render pre-deploy `pytest` imports `main` with the production settings:
        # the test run must never send a real statement.
        return False
    if _schedule_thread is not None:
        return False
    stop = threading.Event()
    thread = threading.Thread(target=_check_forever, args=(stop,), name="member-loan-statement-schedule", daemon=True)
    _schedule_thread = thread
    thread.start()
    return True
