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
