"""/public/inspections/* -- the property inspection walkthrough, open to anyone with the link.

This router is in `main.PUBLIC_ROUTERS`: no session and no app key. It protects
itself instead (tasks/todo/PropertyInspection.md):
- an inspection is reached only by its random uuid4 id; there is deliberately
  no route here that lists inspections;
- responses never carry deal data, only the boolean `linked`;
- every route has a per-IP rate limit, every write needs the CSRF signals and
  a small JSON body, and photos must be JPEGs within the size caps.
Listing, deleting and linking to a Bought Deal are in `routers/inspection.py`,
behind the normal gates.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from BL.inspection.common.inspection_request_guards import inspection_request_guard
from BL.inspection.inspectionPhotos import (
    delete_photo,
    get_photo_full_image,
    get_photo_thumbnail,
    upload_photo_of_inspection_item,
)
from BL.inspection.publicInspection import (
    complete_public_inspection,
    create_public_inspection,
    get_public_inspection,
    update_public_inspection_item,
    update_public_inspection_start_info,
)
from db import get_db
from ReqRes.common.inspection_schemas import (
    InspectionCompleteReq,
    InspectionCreateReq,
    InspectionItemRes,
    InspectionItemUpdateReq,
    InspectionPhotoRes,
    InspectionStartInfoUpdateReq,
    PublicInspectionRes,
)

router = APIRouter()

JPEG_RESPONSE_DOCUMENTATION = {200: {"content": {"image/jpeg": {}}, "description": "The JPEG image."}}


@router.post(
    "/public/inspections",
    response_model=PublicInspectionRes,
    status_code=201,
    dependencies=[Depends(inspection_request_guard("inspection_create", is_json_write=True))],
)
def create_inspection(request: InspectionCreateReq, db: Session = Depends(get_db)):
    return create_public_inspection(db, request)


@router.get(
    "/public/inspections/{inspection_id}",
    response_model=PublicInspectionRes,
    dependencies=[Depends(inspection_request_guard("inspection_read"))],
)
def get_inspection(inspection_id: str, db: Session = Depends(get_db)):
    return get_public_inspection(db, inspection_id)


@router.patch(
    "/public/inspections/{inspection_id}",
    response_model=PublicInspectionRes,
    dependencies=[Depends(inspection_request_guard("inspection_start_info_update", is_json_write=True))],
)
def update_inspection_start_info(inspection_id: str, request: InspectionStartInfoUpdateReq, db: Session = Depends(get_db)):
    return update_public_inspection_start_info(db, inspection_id, request)


@router.patch(
    "/public/inspections/{inspection_id}/items/{item_key}",
    response_model=InspectionItemRes,
    dependencies=[Depends(inspection_request_guard("inspection_item_update", is_json_write=True))],
)
def update_inspection_item(inspection_id: str, item_key: str, request: InspectionItemUpdateReq, db: Session = Depends(get_db)):
    return update_public_inspection_item(db, inspection_id, item_key, request)


@router.post(
    "/public/inspections/{inspection_id}/complete",
    response_model=PublicInspectionRes,
    dependencies=[Depends(inspection_request_guard("inspection_complete", is_json_write=True))],
)
def complete_inspection(inspection_id: str, request: InspectionCompleteReq, db: Session = Depends(get_db)):
    return complete_public_inspection(db, inspection_id, request)


@router.post(
    "/public/inspections/{inspection_id}/items/{item_key}/photos",
    response_model=InspectionPhotoRes,
    status_code=201,
    dependencies=[Depends(inspection_request_guard("inspection_photo_upload"))],
)
async def upload_inspection_photo(
    inspection_id: str,
    item_key: str,
    full_image: UploadFile = File(..., description="The compressed photo: JPEG, at most 1600 px and 4 MB."),
    thumbnail_image: UploadFile = File(..., description="A 320 px JPEG thumbnail, at most 150 KB."),
    db: Session = Depends(get_db),
):
    return await upload_photo_of_inspection_item(db, inspection_id, item_key, full_image, thumbnail_image)


@router.get(
    "/public/inspections/{inspection_id}/photos/{photo_id}/thumbnail",
    response_class=Response,
    responses=JPEG_RESPONSE_DOCUMENTATION,
    dependencies=[Depends(inspection_request_guard("inspection_photo_read"))],
)
def get_inspection_photo_thumbnail(inspection_id: str, photo_id: str, db: Session = Depends(get_db)):
    return get_photo_thumbnail(db, inspection_id, photo_id)


@router.get(
    "/public/inspections/{inspection_id}/photos/{photo_id}/full",
    response_class=Response,
    responses=JPEG_RESPONSE_DOCUMENTATION,
    dependencies=[Depends(inspection_request_guard("inspection_photo_read"))],
)
def get_inspection_photo_full_image(inspection_id: str, photo_id: str, db: Session = Depends(get_db)):
    return get_photo_full_image(db, inspection_id, photo_id)


@router.delete(
    "/public/inspections/{inspection_id}/photos/{photo_id}",
    dependencies=[Depends(inspection_request_guard("inspection_photo_delete"))],
)
def delete_inspection_photo(inspection_id: str, photo_id: str, db: Session = Depends(get_db)):
    delete_photo(db, inspection_id, photo_id)
    return {"message": "Photo deleted"}
