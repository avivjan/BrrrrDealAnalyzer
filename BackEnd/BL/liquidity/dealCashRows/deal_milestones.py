"""The five milestones of an imported BRRRR deal, managed in the liquidity timeline and written back to the deal.

contract signed  -> `contract_date`
purchase closed  -> `buy_closing_date` (the later milestones move with it: their `days_until_*` stay as they are)
rehab completed  -> `days_until_rehab_completed` = date - purchase closing
tenant moved in  -> `days_until_rented` = date - purchase closing
refi closed      -> `days_until_refi` = date - purchase closing

Approving one stores when (`*_approved_at`); a milestone whose planned date passed without an approval is overdue.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Literal, Optional

DealMilestone = Literal["contract_signed", "purchase_closed", "rehab_completed", "tenant_moved_in", "refi_closed"]
DEAL_MILESTONES_IN_ORDER: tuple[DealMilestone, ...] = (
    "contract_signed", "purchase_closed", "rehab_completed", "tenant_moved_in", "refi_closed",
)
_DAYS_AFTER_PURCHASE_CLOSING_COLUMN_BY_MILESTONE = {
    "rehab_completed": "days_until_rehab_completed",
    "tenant_moved_in": "days_until_rented",
    "refi_closed": "days_until_refi",
}


def approved_at_column_of_milestone(milestone: DealMilestone) -> str:
    return f"{milestone}_approved_at"


def planned_date_of_milestone(deal, milestone: DealMilestone) -> date:
    if milestone == "contract_signed":
        return deal.contract_date
    if milestone == "purchase_closed":
        return deal.buy_closing_date
    return deal.buy_closing_date + timedelta(days=int(getattr(deal, _DAYS_AFTER_PURCHASE_CLOSING_COLUMN_BY_MILESTONE[milestone])))


def deal_columns_with_milestone_on(deal, milestone: DealMilestone, new_date: date, approve: bool) -> dict:
    """The deal columns that change when `milestone` moves to `new_date` (and is approved, or set back to planned)."""
    if milestone == "contract_signed":
        changed_columns = {"contract_date": new_date}
    elif milestone == "purchase_closed":
        changed_columns = {"buy_closing_date": new_date}
    else:
        changed_columns = {_DAYS_AFTER_PURCHASE_CLOSING_COLUMN_BY_MILESTONE[milestone]: (new_date - deal.buy_closing_date).days}
    changed_columns[approved_at_column_of_milestone(milestone)] = datetime.now(timezone.utc) if approve else None
    return changed_columns


def milestone_is_overdue(deal, milestone: DealMilestone, today: date) -> bool:
    return getattr(deal, approved_at_column_of_milestone(milestone)) is None and planned_date_of_milestone(deal, milestone) < today


def approved_at_of_milestone(deal, milestone: DealMilestone) -> Optional[datetime]:
    return getattr(deal, approved_at_column_of_milestone(milestone))
