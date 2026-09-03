from sqlalchemy.orm import Session

from DAL.crud.reps import delete_activity_category as _delete_activity_category


def delete_activity_category(db: Session, cat_id: str) -> bool:
    deleted = _delete_activity_category(db, cat_id)
    if deleted:
        db.commit()
    return deleted
