from typing import Union
from sqlalchemy.orm import Session

from ReqRes.common.active_deal_schemas import BrrrActiveDealCreate, FlipActiveDealCreate
from DAL.crud.active_deal import update_brrr_deal, update_flip_deal
from BL.common.deal_response import create_deal_response


def update_deal(db: Session, deal_id: str, deal: Union[BrrrActiveDealCreate, FlipActiveDealCreate]):
    """Returns the updated deal's response, or `None` if no matching row was found.

    Note: IDs might clash if tables use separate auto-increment and we look up just by ID.
    Ideally we need deal_type in query or unique IDs across tables (UUIDs).
    Since we have separate tables with independent integer PKs, ID=1 can exist in both.
    The frontend needs to pass ID AND Type or we need to try both.
    Current API structure `/active-deals/{deal_id}` implies ID uniqueness or we check both.
    If the user provides the payload with the type, we know which one to update.
    But if ID=1 exists in both...
    Assumption: The user selects a specific deal which has a type known to Frontend.
    The backend receives the payload with `deal_type`.
    """
    if deal.deal_type == "BRRRR":
        updated = update_brrr_deal(db, deal_id, deal)
        if updated: return create_deal_response(updated)
    elif deal.deal_type == "FLIP":
        updated = update_flip_deal(db, deal_id, deal)
        if updated: return create_deal_response(updated)

    return None
