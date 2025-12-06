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
    
    # Use default model_dump to ensure all fields are considered,
    # trusting that the frontend sends the complete object.
    update_data = deal_data.model_dump()
    for key, value in update_data.items():
        setattr(db_deal, key, value)
    
    db.commit()
    db.refresh(db_deal)
    return db_deal


def delete_active_deal(db: Session, deal_id: int) -> bool:
    db_deal = db.query(ActiveDeal).filter(ActiveDeal.id == deal_id).first()
    if not db_deal:
        return False
    
    db.delete(db_deal)
    db.commit()
    return True

def duplicate_active_deal(db: Session, deal_id: int) -> ActiveDeal | None:
    original_deal = db.query(ActiveDeal).filter(ActiveDeal.id == deal_id).first()
    if not original_deal:
        return None
    
    # Create new instance with same data
    data = {c.name: getattr(original_deal, c.name) for c in original_deal.__table__.columns if c.name not in ['id', 'created_at', 'updated_at']}
    
    # Append (Copy) to address
    if 'address' in data and data['address']:
        data['address'] = f"{data['address']} (Copy)"
        
    new_deal = ActiveDeal(**data)
    db.add(new_deal)
    db.commit()
    db.refresh(new_deal)
    return new_deal
