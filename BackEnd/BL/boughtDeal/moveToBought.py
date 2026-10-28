from sqlalchemy.orm import Session

from DAL.data_models import BrrrActiveDeal, FlipActiveDeal
from DAL.crud.bought_deal import insert_bought_from_active_brrr, insert_bought_from_active_flip
from BL.boughtDeal.common.first_stage import first_stage_id
from BL.common.deal_response import create_bought_deal_response
from BL.inspection.common.inspection_deal_links import DEAL_BOARD_BOUGHT, DEAL_BOARD_MY_DEALS, deal_link_kind
from DAL.crud.inspection import repoint_inspection_links


def move_to_bought(db: Session, source_deal, deal_type: str):
    """Insert a bought row copied from `source_deal` (already looked up + validated
    by the router) at the pipeline's first stage."""
    stage = first_stage_id(db, deal_type)
    if isinstance(source_deal, BrrrActiveDeal):
        new_deal = insert_bought_from_active_brrr(db, source_deal, stage)
    elif isinstance(source_deal, FlipActiveDeal):
        new_deal = insert_bought_from_active_flip(db, source_deal, stage)
    else:
        return None
    db.flush()
    # Inspections linked to the My Deals deal follow it onto the new Bought Deal
    # (tasks/todo/InspectionLinkToMyDeals.md).
    repoint_inspection_links(
        db,
        deal_link_kind(DEAL_BOARD_MY_DEALS, deal_type).link_column_name,
        source_deal.id,
        deal_link_kind(DEAL_BOARD_BOUGHT, deal_type).link_column_name,
        new_deal.id,
    )
    db.commit()
    db.refresh(new_deal)
    return create_bought_deal_response(new_deal)
