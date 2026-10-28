"""/inspections/* and /bought-deals/{deal_id}/inspections -- property inspections for logged-in users.

Behind the normal gates like every data router: list all inspections, delete
one, and link or unlink an inspection to a Bought Deal. The walkthrough itself
is public (`routers/public_inspection.py`).
"""

from __future__ import annotations

from typing import List, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from BL.inspection.authenticatedInspection import (
    create_inspection_linked_to_bought_deal,
    delete_inspection_and_its_photos,
    get_inspection_deal_link_details,
    link_inspection_to_bought_deal,
    list_all_inspections,
    list_inspections_of_bought_deal,
    unlink_inspection_from_bought_deal,
)
from db import get_db
from ReqRes.common.inspection_schemas import (
    InspectionDealLinkReq,
    InspectionDealLinkRes,
    InspectionForBoughtDealCreateReq,
    InspectionListRowRes,
    PublicInspectionRes,
)

router = APIRouter()


@router.get("/inspections", response_model=List[InspectionListRowRes])
def list_inspections(db: Session = Depends(get_db)):
    return list_all_inspections(db)


@router.delete("/inspections/{inspection_id}")
def delete_inspection(inspection_id: str, db: Session = Depends(get_db)):
    delete_inspection_and_its_photos(db, inspection_id)
    return {"message": "Inspection deleted"}


@router.get("/inspections/{inspection_id}/deal-link", response_model=InspectionDealLinkRes)
def get_inspection_deal_link(inspection_id: str, db: Session = Depends(get_db)):
    return get_inspection_deal_link_details(db, inspection_id)


@router.put("/inspections/{inspection_id}/deal-link", response_model=InspectionDealLinkRes)
def link_inspection_to_deal(inspection_id: str, request: InspectionDealLinkReq, db: Session = Depends(get_db)):
    return link_inspection_to_bought_deal(db, inspection_id, request)


@router.delete("/inspections/{inspection_id}/deal-link", response_model=InspectionDealLinkRes)
def unlink_inspection_from_deal(inspection_id: str, db: Session = Depends(get_db)):
    return unlink_inspection_from_bought_deal(db, inspection_id)


@router.get("/bought-deals/{deal_id}/inspections", response_model=List[InspectionListRowRes])
def list_bought_deal_inspections(deal_id: UUID, deal_type: Literal["BRRRR", "FLIP"] = Query(...), db: Session = Depends(get_db)):
    return list_inspections_of_bought_deal(db, deal_id, deal_type)


@router.post("/bought-deals/{deal_id}/inspections", response_model=PublicInspectionRes, status_code=201)
def create_inspection_for_bought_deal(
    deal_id: UUID,
    request: InspectionForBoughtDealCreateReq,
    deal_type: Literal["BRRRR", "FLIP"] = Query(...),
    db: Session = Depends(get_db),
):
    return create_inspection_linked_to_bought_deal(db, deal_id, deal_type, request)
