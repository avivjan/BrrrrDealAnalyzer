from sqlalchemy.orm import Session

from ReqRes.common.reps_schemas import RepsPersonCreate
from DAL.crud.reps import add_person
from BL.reps.common.mappers import person_to_res


def create_person(db: Session, payload: RepsPersonCreate):
    """Raises on failure (most likely a UNIQUE-name collision); router maps to 400."""
    person = add_person(db, payload)
    return person_to_res(person)
