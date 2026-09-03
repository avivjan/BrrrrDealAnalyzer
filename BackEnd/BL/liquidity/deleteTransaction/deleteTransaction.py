from sqlalchemy.orm import Session

from DAL.crud.liquidity import delete_transaction as _delete_transaction


def delete_transaction(db: Session, txn_id: str) -> bool:
    deleted = _delete_transaction(db, txn_id)
    if deleted:
        db.commit()
    return deleted
