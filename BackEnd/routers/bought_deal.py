"""/bought-deals CRUD + move-from-active."""

from datetime import date, datetime
from typing import Optional, Union, List

from fastapi import APIRouter, Depends, HTTPException, Body, Query, Request
from sqlalchemy.orm import Session

from db import get_db
from ReqRes.common.bought_deal_schemas import (
    BoughtBrrrDealCreate, BoughtBrrrDealRes,
    BoughtFlipDealCreate, BoughtFlipDealRes, DealProjectionSavedToDriveRes, MoveToBoughtReq,
)
from BL.auth.common.audit import record as audit
from BL.boughtDeal.saveProjectionToDrive import save_bought_deal_projection_to_drive as save_bought_deal_projection_to_drive_bl
from BL.common.deal_drive_folder import DealDriveFolderLinkInvalid, DealDriveFolderMissing, DealDriveFolderUploadFailed
from BL.boughtDeal.getBoughtDeals import get_bought_deals as get_bought_deals_bl
from BL.boughtDeal.addBoughtDeal import add_bought_deal as add_bought_deal_bl
from BL.boughtDeal.updateBoughtDeal import StaleDealFormError, update_bought_deal as update_bought_deal_bl
from BL.boughtDeal.deleteBoughtDeal import delete_bought_deal as delete_bought_deal_bl
from BL.boughtDeal.moveToBought import move_to_bought as move_to_bought_bl
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
    try:
        result = add_bought_deal_bl(db, deal)
    except DealDriveFolderLinkInvalid as error:
        raise HTTPException(status_code=422, detail=str(error))
    if result is not None:
        return result
    raise HTTPException(status_code=400, detail="Invalid deal type")

@router.put("/bought-deals/{deal_id}", response_model=Union[BoughtBrrrDealRes, BoughtFlipDealRes])
def update_bought_deal(deal_id: str, deal: Union[BoughtBrrrDealCreate, BoughtFlipDealCreate],
                       updated_at_the_form_was_loaded_with: Optional[datetime] = Query(
                           None, description="The deal's updated_at when your form was loaded: a save is refused (409) if the "
                                             "deal changed since. Leave it out to save regardless."),
                       db: Session = Depends(get_db)):
    try:
        result = update_bought_deal_bl(db, deal_id, deal, updated_at_the_form_was_loaded_with)
    except StaleDealFormError:
        raise HTTPException(status_code=409, detail="This deal was changed elsewhere since your form was loaded")
    except DealDriveFolderLinkInvalid as error:
        raise HTTPException(status_code=422, detail=str(error))
    if result is not None:
        return result
    raise HTTPException(status_code=404, detail="Bought deal not found")

@router.delete("/bought-deals/{deal_id}")
def delete_bought_deal(deal_id: str, deal_type: str = "BRRRR", db: Session = Depends(get_db)):
    if delete_bought_deal_bl(db, deal_id, deal_type):
        return {"message": "Bought deal deleted"}
    raise HTTPException(status_code=404, detail="Bought deal not found")

@router.post("/bought-deals/from-active/{deal_id}", response_model=Union[BoughtBrrrDealRes, BoughtFlipDealRes])
def move_to_bought(deal_id: str, deal_type: str = "BRRRR", data: Optional[MoveToBoughtReq] = Body(None),
                   db: Session = Depends(get_db)):
    """Copy a My Deals deal onto the Bought board. It needs its Google Drive folder link (in the body, or already on the
    My Deals deal): 422 without a valid one."""
    if deal_type == "BRRRR":
        source = get_brrr_deal(db, deal_id)
        if not source:
            raise HTTPException(status_code=404, detail="Source BRRRR deal not found")
    elif deal_type == "FLIP":
        source = get_flip_deal(db, deal_id)
        if not source:
            raise HTTPException(status_code=404, detail="Source FLIP deal not found")
    else:
        raise HTTPException(status_code=400, detail="Invalid deal type")
    try:
        return move_to_bought_bl(db, source, deal_type, data.google_drive_link if data else None)
    except DealDriveFolderLinkInvalid as error:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(error))


@router.post("/bought-deals/{deal_id}/projection-to-drive", response_model=DealProjectionSavedToDriveRes)
def save_bought_deal_projection_to_drive(deal_id: str, request: Request, deal_type: str = "BRRRR",
                                         today: Optional[date] = Query(None, description="The browser's local date, for the file name."),
                                         db: Session = Depends(get_db)):
    """HTML to Drive: the deal's interactive HTML report (as the report download builds it) saved in the deal's own
    Google Drive folder as "<date> deal projection.html". 409 until the deal has its Drive folder link; 502 when Drive
    did not take it."""
    if deal_type not in ("BRRRR", "FLIP"):
        raise HTTPException(status_code=400, detail="Invalid deal type")
    try:
        saved = save_bought_deal_projection_to_drive_bl(db, deal_id, deal_type, today)
    except (DealDriveFolderMissing, DealDriveFolderLinkInvalid):
        raise HTTPException(status_code=409, detail="Add the deal's Google Drive folder link first (https://drive.google.com/drive/folders/...)")
    except DealDriveFolderUploadFailed:
        raise HTTPException(status_code=502, detail="Google Drive did not take the file. Check the Drive folder link and the Drive script, then try again")
    if saved is None:
        raise HTTPException(status_code=404, detail="Bought deal not found")
    audit("bought_deal_projection_saved_to_drive", request, detail={"bought_deal_id": deal_id, "deal_type": deal_type})
    return DealProjectionSavedToDriveRes(file_name=saved.file_name, drive_file_id=saved.drive_file_id, drive_folder_url=saved.drive_folder_url)
