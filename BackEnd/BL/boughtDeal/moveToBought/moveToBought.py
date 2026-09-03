from sqlalchemy.orm import Session

from DAL.data_models import BrrrActiveDeal, FlipActiveDeal
from DAL.crud.bought_deal import insert_bought_from_active_brrr, insert_bought_from_active_flip
from BL.boughtDeal.common.first_stage import first_stage_id
from BL.common.deal_response import create_bought_deal_response


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
    db.commit()
    db.refresh(new_deal)
    return create_bought_deal_response(new_deal)
