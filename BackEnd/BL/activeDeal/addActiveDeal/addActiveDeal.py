from typing import Union
from sqlalchemy.orm import Session

from ReqRes.common.active_deal_schemas import BrrrActiveDealCreate, FlipActiveDealCreate
from DAL.crud.active_deal import add_brrr_deal, add_flip_deal
from BL.common.deal_response import create_deal_response


def add_active_deal(db: Session, deal: Union[BrrrActiveDealCreate, FlipActiveDealCreate]):
    """Returns the created deal's response, or `None` for an unrecognized deal_type."""
    if deal.deal_type == "BRRRR":
        created = add_brrr_deal(db, deal)
        return create_deal_response(created)
    elif deal.deal_type == "FLIP":
        created = add_flip_deal(db, deal)
        return create_deal_response(created)
    return None
