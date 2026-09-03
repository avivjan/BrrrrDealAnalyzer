from sqlalchemy.orm import Session

from DAL.crud.liquidity import delete_recurring as _delete_recurring


def delete_recurring(db: Session, rule_id: str) -> bool:
    deleted = _delete_recurring(db, rule_id)
    if deleted:
        db.commit()
    return deleted
