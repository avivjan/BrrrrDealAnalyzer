"""Which deal an inspection is linked to: a My Deals deal or a Bought Deal, BRRRR or FLIP.

Each of the four (board, type) pairs has its own deal table and its own link
column on `property_inspections`; at most one link is set (a database check).
Everything that reads or writes a link goes through this table.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from uuid import UUID

from DAL.data_models import BoughtBrrrDeal, BoughtFlipDeal, BrrrActiveDeal, FlipActiveDeal, PropertyInspection

DEAL_BOARD_MY_DEALS = "my_deals"
DEAL_BOARD_BOUGHT = "bought"


@dataclass(frozen=True)
class DealLinkKind:
    deal_board: str
    deal_type: str
    deal_model: type
    link_column_name: str


DEAL_LINK_KINDS = (
    DealLinkKind(DEAL_BOARD_MY_DEALS, "BRRRR", BrrrActiveDeal, "linked_active_brrrr_deal_id"),
    DealLinkKind(DEAL_BOARD_MY_DEALS, "FLIP", FlipActiveDeal, "linked_active_flip_deal_id"),
    DealLinkKind(DEAL_BOARD_BOUGHT, "BRRRR", BoughtBrrrDeal, "linked_bought_brrrr_deal_id"),
    DealLinkKind(DEAL_BOARD_BOUGHT, "FLIP", BoughtFlipDeal, "linked_bought_flip_deal_id"),
)


def deal_link_kind(deal_board: str, deal_type: str) -> DealLinkKind:
    return next(kind for kind in DEAL_LINK_KINDS if kind.deal_board == deal_board and kind.deal_type == deal_type)


def linked_deal_of_inspection(inspection: PropertyInspection) -> tuple[Optional[DealLinkKind], Optional[UUID]]:
    for kind in DEAL_LINK_KINDS:
        deal_id = getattr(inspection, kind.link_column_name)
        if deal_id is not None:
            return kind, deal_id
    return None, None


def link_inspection_to(inspection: PropertyInspection, kind: Optional[DealLinkKind], deal_id: Optional[UUID]) -> None:
    """Sets the one link (or none, with `kind=None`) and clears the other three."""

    for each_kind in DEAL_LINK_KINDS:
        setattr(inspection, each_kind.link_column_name, deal_id if each_kind == kind else None)
