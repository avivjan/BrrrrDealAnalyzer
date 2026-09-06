from sqlalchemy.orm import Session

from DAL.crud.reps import list_people as _list_people
from BL.reps.common.mappers import person_to_res


def list_people(db: Session):
    return [person_to_res(p) for p in _list_people(db)]
