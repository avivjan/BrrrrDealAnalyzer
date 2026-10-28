"""Inspection photos: upload, thumbnail, full image, delete.

The browser compresses each camera photo before upload into two JPEGs: the
full image (at most 1600 px) and a 320 px thumbnail. The full image goes to
Google Drive (`inspection_photo_google_drive.py`); the thumbnail is kept in
Postgres so cards and summaries show at once without a Drive round trip.
Only JPEG is accepted (checked by its magic bytes, never by the client's
Content-Type), and every photo is served back as `image/jpeg` with `nosniff`.
"""

from __future__ import annotations

import logging
import uuid

from fastapi import HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from BL.inspection.common.inspection_lookup import find_checklist_item_or_404, find_inspection_or_404, parse_random_id_or_404
from BL.inspection.common.inspection_photo_google_drive import (
    InspectionPhotoStorageUnavailable,
    inspection_drive_folder_name,
    read_inspection_photo_from_drive,
    save_inspection_photo_to_drive,
    trash_inspection_photo_in_drive,
)
from DAL.crud.inspection import count_photos_of_inspection, get_photo_of_inspection
from DAL.data_models import PropertyInspectionPhoto
from ReqRes.common.inspection_schemas import InspectionPhotoRes

logger = logging.getLogger(__name__)

PHOTO_NOT_FOUND = "photo not found"
JPEG_MAGIC_BYTES = b"\xff\xd8\xff"
MAXIMUM_FULL_IMAGE_BYTES = 4 * 1024 * 1024
MAXIMUM_THUMBNAIL_IMAGE_BYTES = 150 * 1024
MAXIMUM_PHOTOS_PER_ITEM = 12
MAXIMUM_PHOTOS_PER_INSPECTION = 150
PHOTO_STORAGE_UNAVAILABLE = "photo_storage_unavailable"


def is_jpeg(image: bytes) -> bool:
    return image.startswith(JPEG_MAGIC_BYTES) and image.endswith(b"\xff\xd9")


async def read_jpeg_upload(upload: UploadFile, maximum_bytes: int, image_description: str) -> bytes:
    declared_size = getattr(upload, "size", None)
    if declared_size is not None and declared_size > maximum_bytes:
        raise HTTPException(status_code=413, detail=f"The {image_description} is larger than {maximum_bytes // 1024} KB.")
    image = await upload.read(maximum_bytes + 1)
    if len(image) > maximum_bytes:
        raise HTTPException(status_code=413, detail=f"The {image_description} is larger than {maximum_bytes // 1024} KB.")
    if not is_jpeg(image):
        raise HTTPException(status_code=415, detail=f"The {image_description} must be a JPEG image.")
    return image


async def upload_photo_of_inspection_item(
    db: Session, raw_inspection_id: str, item_key: str, full_image_upload: UploadFile, thumbnail_image_upload: UploadFile
) -> InspectionPhotoRes:
    inspection = find_inspection_or_404(db, raw_inspection_id)
    find_checklist_item_or_404(item_key)
    if count_photos_of_inspection(db, inspection.id, item_key) >= MAXIMUM_PHOTOS_PER_ITEM:
        raise HTTPException(status_code=409, detail=f"An item can have at most {MAXIMUM_PHOTOS_PER_ITEM} photos.")
    if count_photos_of_inspection(db, inspection.id) >= MAXIMUM_PHOTOS_PER_INSPECTION:
        raise HTTPException(status_code=409, detail=f"An inspection can have at most {MAXIMUM_PHOTOS_PER_INSPECTION} photos.")
    full_image = await read_jpeg_upload(full_image_upload, MAXIMUM_FULL_IMAGE_BYTES, "photo")
    thumbnail_image = await read_jpeg_upload(thumbnail_image_upload, MAXIMUM_THUMBNAIL_IMAGE_BYTES, "thumbnail")

    photo_id = uuid.uuid4()
    folder_name = inspection_drive_folder_name(inspection.inspection_date.isoformat(), inspection.property_address, str(inspection.id))
    try:
        drive_file_id = save_inspection_photo_to_drive(folder_name, f"{item_key} {photo_id.hex[:8]}.jpg", full_image)
    except InspectionPhotoStorageUnavailable:
        raise HTTPException(status_code=503, detail=PHOTO_STORAGE_UNAVAILABLE)
    photo = PropertyInspectionPhoto(
        id=photo_id,
        inspection_id=inspection.id,
        item_key=item_key,
        drive_file_id=drive_file_id,
        thumbnail_jpeg=thumbnail_image,
        full_image_byte_size=len(full_image),
    )
    db.add(photo)
    db.commit()
    db.refresh(photo)
    return InspectionPhotoRes(id=photo.id, item_key=photo.item_key, created_at=photo.created_at)


def _find_photo_or_404(db: Session, raw_inspection_id: str, raw_photo_id: str) -> PropertyInspectionPhoto:
    inspection = find_inspection_or_404(db, raw_inspection_id)
    photo = get_photo_of_inspection(db, inspection.id, parse_random_id_or_404(raw_photo_id, PHOTO_NOT_FOUND))
    if photo is None:
        raise HTTPException(status_code=404, detail=PHOTO_NOT_FOUND)
    return photo


def _jpeg_response(image: bytes) -> Response:
    return Response(
        content=image,
        media_type="image/jpeg",
        headers={
            "Cache-Control": "private, max-age=86400",
            "X-Content-Type-Options": "nosniff",
            "Content-Disposition": "inline",
        },
    )


def get_photo_thumbnail(db: Session, raw_inspection_id: str, raw_photo_id: str) -> Response:
    return _jpeg_response(_find_photo_or_404(db, raw_inspection_id, raw_photo_id).thumbnail_jpeg)


def get_photo_full_image(db: Session, raw_inspection_id: str, raw_photo_id: str) -> Response:
    photo = _find_photo_or_404(db, raw_inspection_id, raw_photo_id)
    try:
        full_image = read_inspection_photo_from_drive(photo.drive_file_id)
    except InspectionPhotoStorageUnavailable:
        raise HTTPException(status_code=503, detail=PHOTO_STORAGE_UNAVAILABLE)
    if not is_jpeg(full_image):
        raise HTTPException(status_code=503, detail=PHOTO_STORAGE_UNAVAILABLE)
    return _jpeg_response(full_image)


def delete_photo(db: Session, raw_inspection_id: str, raw_photo_id: str) -> None:
    photo = _find_photo_or_404(db, raw_inspection_id, raw_photo_id)
    drive_file_id = photo.drive_file_id
    db.delete(photo)
    db.commit()
    try:
        trash_inspection_photo_in_drive(drive_file_id)
    except InspectionPhotoStorageUnavailable:
        logger.warning("inspection photo deleted, but its Drive file could not be trashed")
