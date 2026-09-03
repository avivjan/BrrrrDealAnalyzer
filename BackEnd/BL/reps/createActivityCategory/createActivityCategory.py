from sqlalchemy.orm import Session

from ReqRes.common.reps_schemas import RepsActivityCategoryCreate
from DAL.crud.reps import add_activity_category
from BL.reps.common.mappers import category_to_res


def create_activity_category(db: Session, payload: RepsActivityCategoryCreate):
    """Raises ValueError for a blank name; any other exception also propagates
    -- the router maps both to 400 (with different messages)."""
    cat = add_activity_category(db, payload)
    return category_to_res(cat)
