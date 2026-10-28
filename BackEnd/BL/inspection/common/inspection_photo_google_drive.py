"""Keeps the full-size inspection photos in the company's Google Drive.

Like the loan agreements (`BL/memberLoan/common/member_loan_google_drive.py`),
the photos go through a small Google Apps Script web app owned by
bigwhalesllc@gmail.com (`BackEnd/integrations/google_drive_inspection_photos.gs`),
because a service account has no Drive storage of its own. The script keeps
every photo under the Drive folder "property inspections", in one sub-folder
per inspection, and only ever reads or trashes files inside that folder.

Every request is signed: HMAC-SHA256 with the shared secret over
"<timestamp>\\n<action>\\n<subject>\\n<SHA-256 of the image, or empty>", where
the subject is "<inspection folder>/<file name>" for `save` and the Drive file
id for `read` and `trash`. The script refuses a wrong signature and a
timestamp more than 5 minutes old, so the web app URL alone gives nobody access.

    INSPECTION_PHOTOS_DRIVE_UPLOAD_URL     the Apps Script web app URL (…/exec)
    INSPECTION_PHOTOS_DRIVE_UPLOAD_SECRET  the shared secret, also stored in the script's properties

Both come from the environment only. Tests replace the three public functions
with an in-memory fake (`tests/test_inspection_photos.py`).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import time
import urllib.error
import urllib.request

logger = logging.getLogger(__name__)

PROPERTY_INSPECTIONS_DRIVE_FOLDER_NAME = "property inspections"
DRIVE_REQUEST_TIMEOUT_SECONDS = 60
MAXIMUM_DRIVE_FOLDER_NAME_LENGTH = 120


class InspectionPhotoStorageUnavailable(Exception):
    pass


def drive_request_signature(secret: str, timestamp: int, action: str, subject: str, image_sha256: str) -> str:
    message = f"{timestamp}\n{action}\n{subject}\n{image_sha256}".encode("utf-8")
    return hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()


def inspection_drive_folder_name(inspection_date_iso: str, property_address: str, inspection_id: str) -> str:
    """"2026-10-28 12 Palm Ave, Tampa (3f2a9c1e)": readable in Drive, unique per inspection."""

    safe_address = "".join(character if character.isalnum() or character in " ,.#-" else " " for character in property_address)
    folder_name = f"{inspection_date_iso} {' '.join(safe_address.split())} ({inspection_id[:8]})"
    return folder_name[:MAXIMUM_DRIVE_FOLDER_NAME_LENGTH]


def _configured_drive_url_and_secret() -> tuple[str, str]:
    url = (os.getenv("INSPECTION_PHOTOS_DRIVE_UPLOAD_URL") or "").strip()
    secret = (os.getenv("INSPECTION_PHOTOS_DRIVE_UPLOAD_SECRET") or "").strip()
    if not url or not secret:
        raise InspectionPhotoStorageUnavailable("INSPECTION_PHOTOS_DRIVE_UPLOAD_URL and INSPECTION_PHOTOS_DRIVE_UPLOAD_SECRET must be set")
    if not url.startswith("https://script.google.com/"):
        raise InspectionPhotoStorageUnavailable("INSPECTION_PHOTOS_DRIVE_UPLOAD_URL must be a script.google.com web app URL")
    return url, secret


def build_drive_request_body(*, action: str, secret: str, timestamp: int, subject: str, image: bytes | None = None, **extra: str) -> dict:
    image_sha256 = hashlib.sha256(image).hexdigest() if image is not None else ""
    body = {
        "action": action,
        "subject": subject,
        "image_sha256": image_sha256,
        "timestamp": timestamp,
        "signature": drive_request_signature(secret, timestamp, action, subject, image_sha256),
        **extra,
    }
    if image is not None:
        body["image_base64"] = base64.b64encode(image).decode("ascii")
    return body


def _post_to_drive_script(action: str, subject: str, image: bytes | None = None, **extra: str) -> dict:
    url, secret = _configured_drive_url_and_secret()
    body = json.dumps(build_drive_request_body(action=action, secret=secret, timestamp=int(time.time()), subject=subject, image=image, **extra))
    request = urllib.request.Request(url, data=body.encode("utf-8"), headers={"Content-Type": "application/json"}, method="POST")
    try:
        # Apps Script answers a POST with a redirect to the result, which urllib follows as a GET.
        # nosec B310: the URL was checked above to be https://script.google.com/..., never file: or another scheme.
        with urllib.request.urlopen(request, timeout=DRIVE_REQUEST_TIMEOUT_SECONDS) as response:  # nosec B310
            answer = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError) as error:
        logger.error("inspection photo drive %s failed: %s", action, type(error).__name__)
        raise InspectionPhotoStorageUnavailable(type(error).__name__) from error
    if not isinstance(answer, dict) or not answer.get("ok"):
        reason = str(answer.get("error") if isinstance(answer, dict) else "unexpected answer")[:200]
        logger.error("inspection photo drive %s refused: %s", action, reason)
        raise InspectionPhotoStorageUnavailable(f"the Drive script refused the {action}: {reason}")
    return answer


def save_inspection_photo_to_drive(inspection_folder_name: str, file_name: str, jpeg_image: bytes) -> str:
    """Upload and return the Drive file id. Raises `InspectionPhotoStorageUnavailable`."""

    answer = _post_to_drive_script(
        "save",
        f"{inspection_folder_name}/{file_name}",
        jpeg_image,
        inspection_folder_name=inspection_folder_name,
        file_name=file_name,
    )
    if not answer.get("file_id"):
        raise InspectionPhotoStorageUnavailable("the Drive script returned no file id")
    return str(answer["file_id"])


def read_inspection_photo_from_drive(drive_file_id: str) -> bytes:
    answer = _post_to_drive_script("read", drive_file_id, file_id=drive_file_id)
    try:
        return base64.b64decode(answer["image_base64"], validate=True)
    except (KeyError, ValueError) as error:
        raise InspectionPhotoStorageUnavailable("the Drive script returned no image") from error


def trash_inspection_photo_in_drive(drive_file_id: str) -> None:
    _post_to_drive_script("trash", drive_file_id, file_id=drive_file_id)
