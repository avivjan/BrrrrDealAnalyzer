from sqlalchemy.orm import Session

from DAL.crud.bought_deal import get_all_bought_brrr_deals, get_all_bought_flip_deals
from BL.common.deal_response import create_bought_deal_response


def get_bought_deals(db: Session):
    brrr_deals = get_all_bought_brrr_deals(db)
    flip_deals = get_all_bought_flip_deals(db)

    all_deals = []
    all_deals.extend([create_bought_deal_response(d) for d in brrr_deals])
    all_deals.extend([create_bought_deal_response(d) for d in flip_deals])

    all_deals.sort(key=lambda x: x.created_at, reverse=True)
    return all_deals
