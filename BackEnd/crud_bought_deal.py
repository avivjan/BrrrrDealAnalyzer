from sqlalchemy.orm import Session
from typing import List, Optional

from models import BoughtBrrrDeal, BoughtFlipDeal, BrrrActiveDeal, FlipActiveDeal
from ReqRes.boughtDeal.boughtDealReq import BoughtBrrrDealCreate, BoughtFlipDealCreate


def add_bought_brrr_deal(db: Session, deal_data: BoughtBrrrDealCreate) -> BoughtBrrrDeal:
    data = deal_data.model_dump(mode='json', exclude_unset=True, exclude={'deal_type'})
    db_deal = BoughtBrrrDeal(**data)
    db.add(db_deal)
    db.commit()
    db.refresh(db_deal)
    return db_deal


def add_bought_flip_deal(db: Session, deal_data: BoughtFlipDealCreate) -> BoughtFlipDeal:
    data = deal_data.model_dump(mode='json', exclude_unset=True, exclude={'deal_type'})
    db_deal = BoughtFlipDeal(**data)
    db.add(db_deal)
    db.commit()
    db.refresh(db_deal)
    return db_deal


def get_all_bought_brrr_deals(db: Session) -> List[BoughtBrrrDeal]:
    return db.query(BoughtBrrrDeal).order_by(BoughtBrrrDeal.created_at.desc()).all()


def get_all_bought_flip_deals(db: Session) -> List[BoughtFlipDeal]:
    return db.query(BoughtFlipDeal).order_by(BoughtFlipDeal.created_at.desc()).all()


def update_bought_brrr_deal(db: Session, deal_id: str, deal_data: BoughtBrrrDealCreate) -> Optional[BoughtBrrrDeal]:
    db_deal = db.query(BoughtBrrrDeal).filter(BoughtBrrrDeal.id == deal_id).first()
    if not db_deal:
        return None

    update_data = deal_data.model_dump(mode='json', exclude={'deal_type'})
    for key, value in update_data.items():
        if hasattr(db_deal, key):
            setattr(db_deal, key, value)

    db.commit()
    db.refresh(db_deal)
    return db_deal


def update_bought_flip_deal(db: Session, deal_id: str, deal_data: BoughtFlipDealCreate) -> Optional[BoughtFlipDeal]:
    db_deal = db.query(BoughtFlipDeal).filter(BoughtFlipDeal.id == deal_id).first()
    if not db_deal:
        return None

    update_data = deal_data.model_dump(mode='json', exclude={'deal_type'})
    for key, value in update_data.items():
        if hasattr(db_deal, key):
            setattr(db_deal, key, value)

    db.commit()
    db.refresh(db_deal)
    return db_deal


def delete_bought_brrr_deal(db: Session, deal_id: str) -> bool:
    db_deal = db.query(BoughtBrrrDeal).filter(BoughtBrrrDeal.id == deal_id).first()
    if not db_deal:
        return False
    db.delete(db_deal)
    db.commit()
    return True


def delete_bought_flip_deal(db: Session, deal_id: str) -> bool:
    db_deal = db.query(BoughtFlipDeal).filter(BoughtFlipDeal.id == deal_id).first()
    if not db_deal:
        return False
    db.delete(db_deal)
    db.commit()
    return True


def create_bought_from_active_brrr(db: Session, source_deal: BrrrActiveDeal) -> BoughtBrrrDeal:
    data = {c.name: getattr(source_deal, c.name) for c in source_deal.__table__.columns if c.name not in ['id', 'created_at', 'updated_at']}
    data['bought_stage'] = 1
    data['completed_substages'] = {}
    data['source_deal_id'] = source_deal.id

    new_deal = BoughtBrrrDeal(**data)
    db.add(new_deal)
    db.commit()
    db.refresh(new_deal)
    return new_deal


def create_bought_from_active_flip(db: Session, source_deal: FlipActiveDeal) -> BoughtFlipDeal:
    data = {c.name: getattr(source_deal, c.name) for c in source_deal.__table__.columns if c.name not in ['id', 'created_at', 'updated_at']}
    data['bought_stage'] = 1
    data['completed_substages'] = {}
    data['source_deal_id'] = source_deal.id

    new_deal = BoughtFlipDeal(**data)
    db.add(new_deal)
    db.commit()
    db.refresh(new_deal)
    return new_deal
