"""What a Member Loan endpoint returns: the response, and the e-mails to send after commit."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from BL.memberLoan.common.member_loan_ledger_service import expire_stale_proposals_in_own_transaction


@dataclass
class MemberLoanOutcome:
    response: Any
    notifications_after_commit: list[tuple[str, UUID]] = field(default_factory=list)


def expire_and_list_notifications(db) -> list[tuple[str, UUID]]:
    """Expiry runs before every request, in its own transaction, so its e-mails
    go out whatever happens to the request itself (the router schedules them)."""
    return [(outcome.decision, outcome.event_id) for outcome in expire_stale_proposals_in_own_transaction(db)]
