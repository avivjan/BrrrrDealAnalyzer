from sqlalchemy.orm import Session

from ReqRes.common.reps_schemas import RepsPropertyOption
from DAL.crud.reps import upsert_prospect


def create_prospect(db: Session, name: str) -> RepsPropertyOption:
    """Raises ValueError for a blank name."""
    prospect = upsert_prospect(db, name)
    db.commit()
    db.refresh(prospect)
    return RepsPropertyOption(name=prospect.name, source="prospect")
