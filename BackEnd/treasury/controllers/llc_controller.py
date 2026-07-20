from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from db import get_db
from treasury.schemas.llc_schemas import (
    LLCConfigurationCreate,
    LLCConfigurationUpdate,
    LLCConfigurationRes,
)
from treasury.services import llc_service
from treasury.services.exceptions import NotFoundError

router = APIRouter(prefix="/treasury/llcs", tags=["Treasury - LLC Configuration"])


def _to_res(llc) -> LLCConfigurationRes:
    return LLCConfigurationRes(
        llc_id=llc.llc_id,
        llc_name=llc.llc_name,
        checking_redline_buffer=llc.checking_redline_buffer,
        created_at=llc.created_at.isoformat() if llc.created_at else None,
        updated_at=llc.updated_at.isoformat() if llc.updated_at else None,
    )


@router.get("", response_model=list[LLCConfigurationRes])
def list_llcs(db: Session = Depends(get_db)):
    return [_to_res(llc) for llc in llc_service.list_llcs(db)]


@router.post("", response_model=LLCConfigurationRes, status_code=201)
def create_llc(payload: LLCConfigurationCreate, db: Session = Depends(get_db)):
    return _to_res(llc_service.create_llc(db, payload))


@router.get("/{llc_id}", response_model=LLCConfigurationRes)
def get_llc(llc_id: str, db: Session = Depends(get_db)):
    try:
        return _to_res(llc_service.get_llc(db, llc_id))
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.put("/{llc_id}", response_model=LLCConfigurationRes)
def update_llc(
    llc_id: str,
    payload: LLCConfigurationUpdate,
    db: Session = Depends(get_db),
):
    try:
        return _to_res(llc_service.update_llc(db, llc_id, payload))
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/{llc_id}")
def delete_llc(llc_id: str, db: Session = Depends(get_db)):
    try:
        llc_service.delete_llc(db, llc_id)
        return {
            "message": "LLC deleted (cascaded to its properties and cash-flow history)."
        }
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
