from sqlalchemy.orm import Session

from DAL.crud.bought_deal import delete_bought_brrr_deal, delete_bought_flip_deal


def delete_bought_deal(db: Session, deal_id: str, deal_type: str) -> bool:
    """Returns True if a matching bought deal was deleted."""
    if deal_type == "BRRRR":
        if delete_bought_brrr_deal(db, deal_id): return True
    elif deal_type == "FLIP":
        if delete_bought_flip_deal(db, deal_id): return True

    return False
