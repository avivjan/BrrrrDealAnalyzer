from sqlalchemy.orm import Session

from DAL.crud.reps import list_activity_categories as _list_activity_categories
from BL.reps.common.mappers import category_to_res


def list_activity_categories(db: Session):
    return [category_to_res(c) for c in _list_activity_categories(db)]
