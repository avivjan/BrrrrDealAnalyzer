from sqlalchemy.orm import Session

from DAL.crud.active_deal import get_all_brrr_deals, get_all_flip_deals
from BL.common.deal_response import create_deal_response


def get_active_deals(db: Session):
    brrr_deals = get_all_brrr_deals(db)
    flip_deals = get_all_flip_deals(db)

    all_deals = []
    all_deals.extend([create_deal_response(d) for d in brrr_deals])
    all_deals.extend([create_deal_response(d) for d in flip_deals])

    # Sort by created_at desc
    all_deals.sort(key=lambda x: x.created_at, reverse=True)
    return all_deals
