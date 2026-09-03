from sqlalchemy.orm import Session

from DAL.crud.liquidity import get_all_recurring
from BL.liquidity.common.mappers import recurring_to_res


def list_recurring(db: Session):
    return [recurring_to_res(r) for r in get_all_recurring(db)]
