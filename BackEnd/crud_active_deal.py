from sqlalchemy.orm import Session

from models import ActiveDeal
from ReqRes.activeDeal.activeDealReq import ActiveDealCreate


def add_active_deal(db: Session, deal_data: ActiveDealCreate) -> ActiveDeal:
    db_deal = ActiveDeal(**deal_data.model_dump(exclude_unset=True))
    db.add(db_deal)
    db.commit()
    db.refresh(db_deal)
    return db_deal


def get_all_active_deals(db: Session) -> list[ActiveDeal]:
    return db.query(ActiveDeal).order_by(ActiveDeal.created_at.desc()).all()


def update_active_deal(db: Session, deal_id: int, deal_data: ActiveDealCreate) -> ActiveDeal | None:
    db_deal = db.query(ActiveDeal).filter(ActiveDeal.id == deal_id).first()
    if not db_deal:
        return None
    
    update_data = deal_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_deal, key, value)
    
    db.commit()
    db.refresh(db_deal)
    return db_deal
