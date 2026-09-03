from sqlalchemy.orm import Session

from ReqRes.common.reps_schemas import RepsPersonUpdate
from DAL.crud.reps import update_person as _update_person
from BL.reps.common.mappers import person_to_res


def update_person(db: Session, person_id: str, payload: RepsPersonUpdate):
    """Returns the updated person's response, or `None` if not found."""
    person = _update_person(db, person_id, payload)
    if not person:
        return None
    return person_to_res(person)
