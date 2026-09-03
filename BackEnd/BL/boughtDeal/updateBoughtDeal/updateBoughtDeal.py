from typing import Union
from sqlalchemy.orm import Session

from ReqRes.common.bought_deal_schemas import BoughtBrrrDealCreate, BoughtFlipDealCreate
from DAL.crud.bought_deal import update_bought_brrr_deal, update_bought_flip_deal
from BL.common.deal_response import create_bought_deal_response


def update_bought_deal(db: Session, deal_id: str, deal: Union[BoughtBrrrDealCreate, BoughtFlipDealCreate]):
    """Returns the updated deal's response, or `None` if no matching row was found."""
    if deal.deal_type == "BRRRR":
        updated = update_bought_brrr_deal(db, deal_id, deal)
        if updated: return create_bought_deal_response(updated)
    elif deal.deal_type == "FLIP":
        updated = update_bought_flip_deal(db, deal_id, deal)
        if updated: return create_bought_deal_response(updated)

    return None
