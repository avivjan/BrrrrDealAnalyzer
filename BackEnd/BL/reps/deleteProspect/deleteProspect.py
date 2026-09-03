from sqlalchemy.orm import Session

from DAL.crud.reps import delete_prospect as _delete_prospect


def delete_prospect(db: Session, prospect_id: str) -> bool:
    return _delete_prospect(db, prospect_id)
