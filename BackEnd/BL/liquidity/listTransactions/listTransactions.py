from sqlalchemy.orm import Session

from DAL.crud.liquidity import get_all_transactions
from BL.liquidity.common.mappers import txn_to_res


def list_transactions(db: Session):
    return [txn_to_res(t) for t in get_all_transactions(db)]
