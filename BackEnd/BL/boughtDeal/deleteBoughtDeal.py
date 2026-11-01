import uuid

from sqlalchemy.orm import Session

from BL.liquidity.dealCashRows.deal_cash_rows import DEAL_BOARD_BOUGHT
from BL.liquidity.dealCashRows.liquidity_deals import delete_open_rows_of_deal

from DAL.crud.bought_deal import delete_bought_brrr_deal, delete_bought_flip_deal


def delete_bought_deal(db: Session, deal_id: str, deal_type: str) -> bool:
    """Returns True if a matching bought deal was deleted."""
    if deal_type == "BRRRR":
        if delete_bought_brrr_deal(db, deal_id):
            # Its open liquidity rows go with it; the done ones stay as history.
            delete_open_rows_of_deal(db, DEAL_BOARD_BOUGHT, uuid.UUID(str(deal_id)))
            db.commit()
            return True
    elif deal_type == "FLIP":
        if delete_bought_flip_deal(db, deal_id):
            db.commit()
            return True

    return False
