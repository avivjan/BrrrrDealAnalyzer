"""/reps/* -- REPS (Real Estate Professional Status) tracker."""

import logging
import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, File, Form, UploadFile
from sqlalchemy.orm import Session

from db import get_db
from ReqRes.reps.log.logReq import RepsLogCreate
from ReqRes.reps.log.logRes import RepsLogRes
from ReqRes.reps.entries.entriesRes import RepsEntriesEnvelope
from ReqRes.reps.uploadBatch.uploadBatchRes import RepsUploadBatchRes
from ReqRes.reps.listProperties.listPropertiesRes import RepsPropertyOption
from ReqRes.reps.createProspect.createProspectReq import RepsPropertyCreate
from ReqRes.reps.listPeople.listPeopleRes import RepsPersonRes
from ReqRes.reps.createPerson.createPersonReq import RepsPersonCreate
from ReqRes.reps.updatePerson.updatePersonReq import RepsPersonUpdate
from ReqRes.reps.listActivityCategories.listActivityCategoriesRes import RepsActivityCategoryRes
from ReqRes.reps.createActivityCategory.createActivityCategoryReq import RepsActivityCategoryCreate
from BL.reps.common import reps_service
from BL.reps.common.valid_users import VALID_REPS_USERS
from BL.reps.log import create_log as create_log_bl
from BL.reps.entries import get_entries as get_entries_bl
from BL.reps.uploadBatch import upload_batch as upload_batch_bl
from BL.reps.upload import upload_single as upload_single_bl
from BL.reps.listProperties import list_property_options as list_property_options_bl
from BL.reps.createProspect import create_prospect as create_prospect_bl
from BL.reps.deleteProspect import delete_prospect as delete_prospect_bl
from BL.reps.listPeople import list_people as list_people_bl
from BL.reps.createPerson import create_person as create_person_bl
from BL.reps.updatePerson import update_person as update_person_bl
from BL.reps.deletePerson import delete_person as delete_person_bl
from BL.reps.listActivityCategories import list_activity_categories as list_activity_categories_bl
from BL.reps.createActivityCategory import create_activity_category as create_activity_category_bl
from BL.reps.deleteActivityCategory import delete_activity_category as delete_activity_category_bl
from BL.reps.configStatus import get_config_status as get_config_status_bl

logger = logging.getLogger(__name__)

router = APIRouter()


# Upload caps (SECURITY_PLAN.md F-04 / F-08): the Netlify proxy in front of
# the API allows 25 MB per request, so the batch is bounded to fit under it.
MAX_UPLOAD_FILES = 10
MAX_UPLOAD_BYTES_PER_FILE = 25 * 1024 * 1024
MAX_UPLOAD_BYTES_TOTAL = 25 * 1024 * 1024


def _require_reps_user(user: str) -> str:
    if user not in VALID_REPS_USERS:
        # The valid ids are not listed back: an unknown caller learns nothing.
        raise HTTPException(status_code=400, detail="unknown REPS user")
    return user


def _internal_error(what: str) -> HTTPException:
    """A 500 with a reference id instead of the exception text (F-09)."""
    ref = uuid.uuid4().hex[:12]
    logger.exception("%s ref=%s", what, ref)
    return HTTPException(status_code=500, detail=f"{what} (ref {ref})")


async def _read_uploads(files: List[UploadFile]) -> List[tuple[str, Optional[str], bytes]]:
    """Read the uploads with the caps enforced before anything is buffered."""
    if len(files) > MAX_UPLOAD_FILES:
        raise HTTPException(status_code=400, detail=f"At most {MAX_UPLOAD_FILES} files per upload.")
    items: List[tuple[str, Optional[str], bytes]] = []
    total = 0
    for f in files:
        declared = getattr(f, "size", None)
        if declared is not None and declared > MAX_UPLOAD_BYTES_PER_FILE:
            raise HTTPException(status_code=413, detail="A file exceeds the 25 MB limit.")
        contents = await f.read(MAX_UPLOAD_BYTES_PER_FILE + 1)
        if len(contents) > MAX_UPLOAD_BYTES_PER_FILE:
            raise HTTPException(status_code=413, detail="A file exceeds the 25 MB limit.")
        total += len(contents)
        if total > MAX_UPLOAD_BYTES_TOTAL:
            raise HTTPException(status_code=413, detail="The upload exceeds the 25 MB limit.")
        items.append((f.filename or "evidence", f.content_type, contents))
    return items


@router.post("/reps/log", response_model=RepsLogRes, status_code=201)
def reps_log_route(payload: RepsLogCreate, db: Session = Depends(get_db)):
    """Append a new REPS entry to the user's Google Sheet (append-only).

    Evidence: each `evidence_items` entry becomes a clickable named link in
    the Sheet's Evidence column (rich text). The user types the label in
    the modal so the auditor sees `Closing meeting` instead of a 240-char
    GCS URL.

    Location: `location_snapshots` get rendered as breadcrumbs (START/STOP/
    PAUSE/RESUME/BOOKMARK/MANUAL/PHOTO) so an auditor can verify the user
    stayed at the property during the session.
    """

    _require_reps_user(payload.user)

    try:
        return create_log_bl(db, payload)
    except reps_service.RepsConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except reps_service.RepsValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception:
        raise _internal_error("Sheet append failed")


@router.get("/reps/entries", response_model=RepsEntriesEnvelope)
def reps_entries_route(user: str = Query(...)):
    """Read the user's full sheet history and return entries + computed stats."""
    _require_reps_user(user)
    try:
        return get_entries_bl(user)
    except reps_service.RepsConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except reps_service.RepsValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception:
        raise _internal_error("Sheet read failed")


@router.post("/reps/upload-batch", response_model=RepsUploadBatchRes)
async def reps_upload_batch_route(
    user: str = Form(...),
    property_name: Optional[str] = Form(None),
    activity_category: Optional[str] = Form(None),
    log_timestamp: Optional[str] = Form(None),
    files: List[UploadFile] = File(...),
):
    """Upload one or many evidence files into a per-log GCS sub-folder.

    The folder + per-file URLs are returned to the frontend, which then sends
    them back inside the `/reps/log` payload so the Sheet stores both the
    folder URL (auditor's index page) and each file URL.
    """

    _require_reps_user(user)
    if not files:
        raise HTTPException(status_code=400, detail="At least one file is required.")

    log_dt: Optional[datetime] = None
    if log_timestamp:
        try:
            log_dt = datetime.fromisoformat(log_timestamp.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(
                status_code=400, detail="log_timestamp must be ISO-8601."
            )

    items = await _read_uploads(files)

    try:
        return upload_batch_bl(
            user=user,
            property_name=property_name,
            activity_category=activity_category,
            log_timestamp=log_dt,
            items=items,
        )
    except reps_service.RepsConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except reps_service.RepsValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception:
        raise _internal_error("Upload failed")


@router.post("/reps/upload")
async def reps_upload_route(
    user: str = Form(...),
    file: UploadFile = File(...),
):
    """Single-file convenience shim — kept for backward compatibility.

    New clients should call `/reps/upload-batch`.
    """

    _require_reps_user(user)
    (filename, content_type, contents), = await _read_uploads([file])
    try:
        url = upload_single_bl(
            user=user,
            file_bytes=contents,
            filename=filename,
            content_type=content_type,
        )
    except reps_service.RepsConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except reps_service.RepsValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception:
        raise _internal_error("Upload failed")

    return {"url": url, "filename": filename}


@router.get("/reps/properties", response_model=List[RepsPropertyOption])
def reps_properties_route(db: Session = Depends(get_db)):
    """Bought-deal addresses (priority) + saved prospects."""
    return list_property_options_bl(db)


@router.post("/reps/properties", response_model=RepsPropertyOption, status_code=201)
def reps_create_prospect_route(payload: RepsPropertyCreate, db: Session = Depends(get_db)):
    try:
        return create_prospect_bl(db, payload.name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.delete("/reps/properties/{prospect_id}")
def reps_delete_prospect_route(prospect_id: str, db: Session = Depends(get_db)):
    if not delete_prospect_bl(db, prospect_id):
        raise HTTPException(status_code=404, detail="Prospect not found")
    return {"message": "Prospect deleted"}


@router.get("/reps/people", response_model=List[RepsPersonRes])
def reps_list_people_route(db: Session = Depends(get_db)):
    return list_people_bl(db)


@router.post("/reps/people", response_model=RepsPersonRes, status_code=201)
def reps_create_person_route(payload: RepsPersonCreate, db: Session = Depends(get_db)):
    try:
        return create_person_bl(db, payload)
    except Exception:
        # most likely a UNIQUE-name collision; the driver's text stays in the log
        logger.warning("Could not add REPS person %r", payload.name, exc_info=True)
        raise HTTPException(status_code=400, detail="Could not add person: a person with that name may already exist")


@router.put("/reps/people/{person_id}", response_model=RepsPersonRes)
def reps_update_person_route(
    person_id: str, payload: RepsPersonUpdate, db: Session = Depends(get_db)
):
    result = update_person_bl(db, person_id, payload)
    if not result:
        raise HTTPException(status_code=404, detail="Person not found")
    return result


@router.delete("/reps/people/{person_id}")
def reps_delete_person_route(person_id: str, db: Session = Depends(get_db)):
    if not delete_person_bl(db, person_id):
        raise HTTPException(status_code=404, detail="Person not found")
    return {"message": "Person deleted"}


@router.get("/reps/activity-categories", response_model=List[RepsActivityCategoryRes])
def reps_list_activity_categories_route(db: Session = Depends(get_db)):
    return list_activity_categories_bl(db)


@router.post("/reps/activity-categories", response_model=RepsActivityCategoryRes, status_code=201)
def reps_create_activity_category_route(
    payload: RepsActivityCategoryCreate, db: Session = Depends(get_db)
):
    try:
        return create_activity_category_bl(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception:
        logger.warning("Could not add REPS category %r", payload.name, exc_info=True)
        raise HTTPException(status_code=400, detail="Could not add category: a category with that name may already exist")


@router.delete("/reps/activity-categories/{cat_id}")
def reps_delete_activity_category_route(cat_id: str, db: Session = Depends(get_db)):
    if not delete_activity_category_bl(db, cat_id):
        raise HTTPException(status_code=404, detail="Activity category not found")
    return {"message": "Activity category deleted"}


@router.get("/reps/config-status")
def reps_config_status_route():
    """Lightweight probe so the frontend can show a setup banner if env is missing."""
    return get_config_status_bl()
