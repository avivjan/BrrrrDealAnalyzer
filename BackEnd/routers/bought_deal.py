"""/bought-deals CRUD + move-from-active."""

from typing import Union, List

from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session

from db import get_db
from ReqRes.common.bought_deal_schemas import (
    BoughtBrrrDealCreate, BoughtBrrrDealRes,
    BoughtFlipDealCreate, BoughtFlipDealRes,
)
from BL.boughtDeal.getBoughtDeals.getBoughtDeals import get_bought_deals as get_bought_deals_bl
from BL.boughtDeal.addBoughtDeal.addBoughtDeal import add_bought_deal as add_bought_deal_bl
from BL.boughtDeal.updateBoughtDeal.updateBoughtDeal import update_bought_deal as update_bought_deal_bl
from BL.boughtDeal.deleteBoughtDeal.deleteBoughtDeal import delete_bought_deal as delete_bought_deal_bl
from BL.boughtDeal.moveToBought.moveToBought import move_to_bought as move_to_bought_bl
from DAL.crud.active_deal import get_brrr_deal, get_flip_deal

router = APIRouter()


@router.get("/bought-deals", response_model=List[Union[BoughtBrrrDealRes, BoughtFlipDealRes]])
def get_bought_deals(db: Session = Depends(get_db)):
    return get_bought_deals_bl(db)

@router.post("/bought-deals", response_model=Union[BoughtBrrrDealRes, BoughtFlipDealRes])
def add_bought_deal(
    deal: Union[BoughtBrrrDealCreate, BoughtFlipDealCreate] = Body(..., discriminator='deal_type'),
    db: Session = Depends(get_db)
):
    result = add_bought_deal_bl(db, deal)
    if result is not None:
        return result
    raise HTTPException(status_code=400, detail="Invalid deal type")

@router.put("/bought-deals/{deal_id}", response_model=Union[BoughtBrrrDealRes, BoughtFlipDealRes])
def update_bought_deal(deal_id: str, deal: Union[BoughtBrrrDealCreate, BoughtFlipDealCreate], db: Session = Depends(get_db)):
    result = update_bought_deal_bl(db, deal_id, deal)
    if result is not None:
        return result
    raise HTTPException(status_code=404, detail="Bought deal not found")

@router.delete("/bought-deals/{deal_id}")
def delete_bought_deal(deal_id: str, deal_type: str = "BRRRR", db: Session = Depends(get_db)):
    if delete_bought_deal_bl(db, deal_id, deal_type):
        return {"message": "Bought deal deleted"}
    raise HTTPException(status_code=404, detail="Bought deal not found")

@router.post("/bought-deals/from-active/{deal_id}", response_model=Union[BoughtBrrrDealRes, BoughtFlipDealRes])
def move_to_bought(deal_id: str, deal_type: str = "BRRRR", db: Session = Depends(get_db)):
    if deal_type == "BRRRR":
        source = get_brrr_deal(db, deal_id)
        if not source:
            raise HTTPException(status_code=404, detail="Source BRRRR deal not found")
        return move_to_bought_bl(db, source, "BRRRR")
    elif deal_type == "FLIP":
        source = get_flip_deal(db, deal_id)
        if not source:
            raise HTTPException(status_code=404, detail="Source FLIP deal not found")
        return move_to_bought_bl(db, source, "FLIP")

    raise HTTPException(status_code=400, detail="Invalid deal type")
