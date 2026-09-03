from typing import Union
from sqlalchemy.orm import Session

from ReqRes.common.bought_deal_schemas import BoughtBrrrDealCreate, BoughtFlipDealCreate
from DAL.crud.bought_deal import add_bought_brrr_deal, add_bought_flip_deal
from BL.common.deal_response import create_bought_deal_response


def add_bought_deal(db: Session, deal: Union[BoughtBrrrDealCreate, BoughtFlipDealCreate]):
    """Returns the created deal's response, or `None` for an unrecognized deal_type."""
    if deal.deal_type == "BRRRR":
        created = add_bought_brrr_deal(db, deal)
        return create_bought_deal_response(created)
    elif deal.deal_type == "FLIP":
        created = add_bought_flip_deal(db, deal)
        return create_bought_deal_response(created)
    return None
