"""Member Loan configuration, read from the environment on every call.

    MEMBER_LOAN_LENDER_USERNAME     passkey username of the Lender (Aviv)
    MEMBER_LOAN_YARDEN_USERNAME     passkey username of the other member (Yarden)
    MEMBER_LOAN_ALLOWED_USERNAMES   comma-separated; must name exactly those two
    MEMBER_LOAN_LENDER_EMAIL        where the Lender's mail goes
    MEMBER_LOAN_YARDEN_EMAIL        where the other member's mail goes
    MEMBER_LOAN_SENDER_ADDRESS      Gmail account that sends (default bigwhalesllc@gmail.com);
                                    its app password is EMAIL_PASSWORD, as for offers
    MEMBER_LOAN_APP_ORIGIN          link base in e-mails (default AUTH_APP_ORIGIN, then the
                                    first allowed origin)
    MEMBER_LOAN_EMAIL_DRY_RUN       true (default) | false -- statements are only rendered
                                    to a file until the owner turns this off
    MEMBER_LOAN_WRITES_PER_HOUR     proposals and decisions per member per hour (default 30)

Nothing here ever reaches the frontend. A missing or inconsistent member
configuration makes every /member-loan route answer 503: the module fails
closed, never open.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from BL.auth.common import settings as auth_settings

# The loan and the company are in Florida (decision D3): the clock for the
# monthly statement, the month lock and the future-date limit.
LOAN_TIME_ZONE = ZoneInfo("America/New_York")
PENDING_PROPOSAL_LIFETIME_DAYS = 14
DEFAULT_SENDER_ADDRESS = "bigwhalesllc@gmail.com"


class MemberLoanMisconfigured(RuntimeError):
    pass


@dataclass(frozen=True)
class MemberLoanSettings:
    lender_username: str
    yarden_username: str
    lender_email: Optional[str]
    yarden_email: Optional[str]
    sender_address: str
    app_origin: str
    statement_email_dry_run: bool
    writes_per_hour_per_member: int


def _env(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip()


def _optional_email(name: str) -> Optional[str]:
    value = _env(name)
    if not value:
        return None
    if "@" not in value or any(c.isspace() for c in value) or "," in value:
        raise MemberLoanMisconfigured(f"{name} is not a single e-mail address")
    return value


def load_member_loan_settings() -> MemberLoanSettings:
    lender_username = _env("MEMBER_LOAN_LENDER_USERNAME")
    yarden_username = _env("MEMBER_LOAN_YARDEN_USERNAME")
    allowed_usernames = {u.strip() for u in _env("MEMBER_LOAN_ALLOWED_USERNAMES").split(",") if u.strip()}
    if not lender_username or not yarden_username or lender_username == yarden_username:
        raise MemberLoanMisconfigured("the two member usernames must be set and different")
    if allowed_usernames != {lender_username, yarden_username}:
        raise MemberLoanMisconfigured("MEMBER_LOAN_ALLOWED_USERNAMES must name exactly the two members")
    try:
        writes_per_hour = int(_env("MEMBER_LOAN_WRITES_PER_HOUR", "30"))
    except ValueError as exc:
        raise MemberLoanMisconfigured("MEMBER_LOAN_WRITES_PER_HOUR must be a whole number") from exc
    origin = _env("MEMBER_LOAN_APP_ORIGIN") or _env("AUTH_APP_ORIGIN") or auth_settings.allowed_origins()[0]
    return MemberLoanSettings(
        lender_username=lender_username,
        yarden_username=yarden_username,
        lender_email=_optional_email("MEMBER_LOAN_LENDER_EMAIL"),
        yarden_email=_optional_email("MEMBER_LOAN_YARDEN_EMAIL"),
        sender_address=_env("MEMBER_LOAN_SENDER_ADDRESS", DEFAULT_SENDER_ADDRESS),
        app_origin=origin.rstrip("/"),
        statement_email_dry_run=_env("MEMBER_LOAN_EMAIL_DRY_RUN", "true").lower() != "false",
        writes_per_hour_per_member=max(1, writes_per_hour),
    )


def utc_now() -> datetime:
    """The server clock. Tests replace it; user actions never use it as "today"."""
    return datetime.now(timezone.utc)


def new_york_today() -> date:
    """Today in the loan's time zone: used only for server-side guards and the cron."""
    return utc_now().astimezone(LOAN_TIME_ZONE).date()
