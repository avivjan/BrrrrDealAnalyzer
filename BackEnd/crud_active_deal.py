from sqlalchemy.orm import Session
from typing import Union, List

from models import BrrrActiveDeal, FlipActiveDeal
from ReqRes.activeDeal.activeDealReq import BrrrActiveDealCreate, FlipActiveDealCreate


def add_brrr_deal(db: Session, deal_data: BrrrActiveDealCreate) -> BrrrActiveDeal:
    data = deal_data.model_dump(exclude_unset=True, exclude={'deal_type'})
    db_deal = BrrrActiveDeal(**data)
    db.add(db_deal)
    db.commit()
    db.refresh(db_deal)
    return db_deal


def add_flip_deal(db: Session, deal_data: FlipActiveDealCreate) -> FlipActiveDeal:
    data = deal_data.model_dump(exclude_unset=True, exclude={'deal_type'})
    db_deal = FlipActiveDeal(**data)
    db.add(db_deal)
    db.commit()
    db.refresh(db_deal)
    return db_deal


def get_all_brrr_deals(db: Session) -> List[BrrrActiveDeal]:
    return db.query(BrrrActiveDeal).order_by(BrrrActiveDeal.created_at.desc()).all()


def get_all_flip_deals(db: Session) -> List[FlipActiveDeal]:
    return db.query(FlipActiveDeal).order_by(FlipActiveDeal.created_at.desc()).all()


def update_brrr_deal(db: Session, deal_id: str, deal_data: BrrrActiveDealCreate) -> BrrrActiveDeal | None:
    db_deal = db.query(BrrrActiveDeal).filter(BrrrActiveDeal.id == deal_id).first()
    if not db_deal:
        return None
    
    update_data = deal_data.model_dump(exclude={'deal_type'})
    for key, value in update_data.items():
        if hasattr(db_deal, key):
            setattr(db_deal, key, value)
    
    db.commit()
    db.refresh(db_deal)
    return db_deal


def update_flip_deal(db: Session, deal_id: str, deal_data: FlipActiveDealCreate) -> FlipActiveDeal | None:
    db_deal = db.query(FlipActiveDeal).filter(FlipActiveDeal.id == deal_id).first()
    if not db_deal:
        return None
    
    update_data = deal_data.model_dump(exclude={'deal_type'})
    for key, value in update_data.items():
        if hasattr(db_deal, key):
            setattr(db_deal, key, value)
    
    db.commit()
    db.refresh(db_deal)
    return db_deal


def delete_brrr_deal(db: Session, deal_id: str) -> bool:
    db_deal = db.query(BrrrActiveDeal).filter(BrrrActiveDeal.id == deal_id).first()
    if not db_deal:
        return False
    
    db.delete(db_deal)
    db.commit()
    return True


def delete_flip_deal(db: Session, deal_id: str) -> bool:
    db_deal = db.query(FlipActiveDeal).filter(FlipActiveDeal.id == deal_id).first()
    if not db_deal:
        return False
    
    db.delete(db_deal)
    db.commit()
    return True


def duplicate_brrr_deal(db: Session, deal_id: str) -> BrrrActiveDeal | None:
    original_deal = db.query(BrrrActiveDeal).filter(BrrrActiveDeal.id == deal_id).first()
    if not original_deal:
        return None
    
    # Create new instance with same data
    data = {c.name: getattr(original_deal, c.name) for c in original_deal.__table__.columns if c.name not in ['id', 'created_at', 'updated_at']}
    
    if 'address' in data and data['address']:
        data['address'] = f"{data['address']} (Copy)"
        
    new_deal = BrrrActiveDeal(**data)
    db.add(new_deal)
    db.commit()
    db.refresh(new_deal)
    return new_deal

def duplicate_flip_deal(db: Session, deal_id: str) -> FlipActiveDeal | None:
    original_deal = db.query(FlipActiveDeal).filter(FlipActiveDeal.id == deal_id).first()
    if not original_deal:
        return None
    
    # Create new instance with same data
    data = {c.name: getattr(original_deal, c.name) for c in original_deal.__table__.columns if c.name not in ['id', 'created_at', 'updated_at']}
    
    if 'address' in data and data['address']:
        data['address'] = f"{data['address']} (Copy)"
        
    new_deal = FlipActiveDeal(**data)
    db.add(new_deal)
    db.commit()
    db.refresh(new_deal)
    return new_deal
