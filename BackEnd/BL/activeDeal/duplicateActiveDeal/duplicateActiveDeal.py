from sqlalchemy.orm import Session

from DAL.crud.active_deal import duplicate_brrr_deal, duplicate_flip_deal
from BL.common.deal_response import create_deal_response


def duplicate_deal(db: Session, deal_id: str, deal_type: str):
    """Returns the duplicated deal's response, or `None` if no matching row was found."""
    if deal_type == "BRRRR":
        new_deal = duplicate_brrr_deal(db, deal_id)
        if new_deal: return create_deal_response(new_deal)
    elif deal_type == "FLIP":
        new_deal = duplicate_flip_deal(db, deal_id)
        if new_deal: return create_deal_response(new_deal)

    return None
