"""/active-deals CRUD + duplicate."""

from typing import Union, List

from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session

from db import get_db
from ReqRes.common.active_deal_schemas import (
    BrrrActiveDealCreate, BrrrActiveDealRes,
    FlipActiveDealCreate, FlipActiveDealRes,
)
from BL.activeDeal.getActiveDeals.getActiveDeals import get_active_deals as get_active_deals_bl
from BL.activeDeal.addActiveDeal.addActiveDeal import add_active_deal as add_active_deal_bl
from BL.activeDeal.updateActiveDeal.updateActiveDeal import update_deal as update_deal_bl
from BL.activeDeal.deleteActiveDeal.deleteActiveDeal import delete_deal as delete_deal_bl
from BL.activeDeal.duplicateActiveDeal.duplicateActiveDeal import duplicate_deal as duplicate_deal_bl

router = APIRouter()


@router.get("/active-deals", response_model=List[Union[BrrrActiveDealRes, FlipActiveDealRes]])
def get_active_deals(db: Session = Depends(get_db)):
    return get_active_deals_bl(db)


@router.post("/active-deals", response_model=Union[BrrrActiveDealRes, FlipActiveDealRes])
def add_active_deal(
    deal: Union[BrrrActiveDealCreate, FlipActiveDealCreate] = Body(..., discriminator='deal_type'),
    db: Session = Depends(get_db)
):
    result = add_active_deal_bl(db, deal)
    if result is not None:
        return result
    raise HTTPException(status_code=400, detail="Invalid deal type")

@router.put("/active-deals/{deal_id}", response_model=Union[BrrrActiveDealRes, FlipActiveDealRes])
def update_deal(deal_id: str, deal: Union[BrrrActiveDealCreate, FlipActiveDealCreate], db: Session = Depends(get_db)):
    result = update_deal_bl(db, deal_id, deal)
    if result is not None:
        return result
    raise HTTPException(status_code=404, detail="Deal not found")

@router.delete("/active-deals/{deal_id}")
def delete_deal(deal_id: str, deal_type: str = "BRRRR", db: Session = Depends(get_db)):
    if delete_deal_bl(db, deal_id, deal_type):
        return {"message": "Deal deleted"}
    raise HTTPException(status_code=404, detail="Deal not found")

@router.post("/active-deals/{deal_id}/duplicate", response_model=Union[BrrrActiveDealRes, FlipActiveDealRes])
def duplicate_deal(deal_id: str, deal_type: str = "BRRRR", db: Session = Depends(get_db)):
    result = duplicate_deal_bl(db, deal_id, deal_type)
    if result is not None:
        return result
    raise HTTPException(status_code=404, detail="Deal not found")
