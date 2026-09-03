from sqlalchemy.orm import Session

from DAL.crud.reps import delete_person as _delete_person


def delete_person(db: Session, person_id: str) -> bool:
    deleted = _delete_person(db, person_id)
    if deleted:
        db.commit()
    return deleted
