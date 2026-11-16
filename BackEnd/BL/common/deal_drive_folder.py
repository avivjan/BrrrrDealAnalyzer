"""A Bought deal's own Google Drive folder: its "Google Drive Link" (tasks/todo/DealDriveFolderRehabSummaryAndProjection.md).

The link must be a Google Drive *folder* link; only its folder id is used. Files are saved into that folder (or its
"Rehab" subfolder) through a small Google Apps Script web app owned by the owner's personal Google account
(`BackEnd/integrations/google_drive_deal_folders.gs`): a service account cannot keep files in a personal Gmail Drive.

Every request is signed: HMAC-SHA256 with the shared secret over
"<timestamp>\\n<folder id>/<subfolder>/<file name>\\n<SHA-256 of the file>". The script refuses a wrong signature, a
file whose SHA-256 differs, a timestamp more than 5 minutes old, a folder this account does not own, any subfolder
but "Rehab", and any file but a .pdf, .csv or .html.

    DEAL_DRIVE_FOLDERS_UPLOAD_URL     the Apps Script web app URL (…/exec)
    DEAL_DRIVE_FOLDERS_UPLOAD_SECRET  the shared secret, also stored in the script's properties

Both come from the environment only. Tests replace `save_file_to_deal_drive_folder` where it is used.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import re
import time
import urllib.error
import urllib.request
from typing import Optional
from urllib.parse import urlsplit

logger = logging.getLogger(__name__)

UPLOAD_TIMEOUT_SECONDS = 60
REHAB_SUBFOLDER_NAME = "Rehab"
DEAL_FOLDER_ITSELF = ""
ALLOWED_SUBFOLDER_NAMES = (DEAL_FOLDER_ITSELF, REHAB_SUBFOLDER_NAME)
DRIVE_FOLDER_ID_PATTERN = re.compile(r"[A-Za-z0-9_-]{10,100}")
# https://drive.google.com/drive/folders/<id> and https://drive.google.com/drive/u/<n>/folders/<id>
DRIVE_FOLDER_PATH_PATTERN = re.compile(r"/drive/(?:u/\d+/)?folders/(?P<folder_id>[A-Za-z0-9_-]{10,100})/?")
DRIVE_FOLDER_LINK_HELP = "Paste the link of a Google Drive folder: https://drive.google.com/drive/folders/…"


class DealDriveFolderLinkInvalid(ValueError):
    """The text is not a Google Drive folder link (the message is safe to show)."""


class DealDriveFolderMissing(Exception):
    """The deal has no Google Drive folder link yet."""


class DealDriveFolderUploadFailed(Exception):
    pass


def drive_folder_id_from_link(link: Optional[str]) -> str:
    """The folder id of a Google Drive folder link. Raises `DealDriveFolderLinkInvalid` for anything else."""
    text = (link or "").strip()
    if not text:
        raise DealDriveFolderLinkInvalid(f"The Google Drive Link is required. {DRIVE_FOLDER_LINK_HELP}")
    parts = urlsplit(text)
    match = DRIVE_FOLDER_PATH_PATTERN.fullmatch(parts.path or "")
    if parts.scheme != "https" or parts.netloc != "drive.google.com" or match is None or parts.username or parts.password:
        raise DealDriveFolderLinkInvalid(f"That is not a Google Drive folder link. {DRIVE_FOLDER_LINK_HELP}")
    return match["folder_id"]


def drive_folder_id_of_deal(deal) -> str:
    """The deal's folder id. Raises `DealDriveFolderMissing` (no link) or `DealDriveFolderLinkInvalid` (a bad one)."""
    if not (getattr(deal, "google_drive_link", None) or "").strip():
        raise DealDriveFolderMissing("add the deal's Google Drive folder link first")
    return drive_folder_id_from_link(deal.google_drive_link)


def upload_signature(secret: str, timestamp: int, subject: str, file_sha256: str) -> str:
    message = f"{timestamp}\n{subject}\n{file_sha256}".encode("utf-8")
    return hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()


def build_upload_request_body(*, folder_id: str, subfolder_name: str, file_name: str, file_bytes: bytes, secret: str,
                              timestamp: int) -> dict:
    file_sha256 = hashlib.sha256(file_bytes).hexdigest()
    subject = f"{folder_id}/{subfolder_name}/{file_name}"
    return {
        "folder_id": folder_id,
        "subfolder_name": subfolder_name,
        "file_name": file_name,
        "file_base64": base64.b64encode(file_bytes).decode("ascii"),
        "file_sha256": file_sha256,
        "timestamp": timestamp,
        "signature": upload_signature(secret, timestamp, subject, file_sha256),
    }


def save_file_to_deal_drive_folder(folder_id: str, subfolder_name: str, file_name: str, file_bytes: bytes) -> tuple[str, str]:
    """Upload one .pdf, .csv or .html into the deal folder (or its "Rehab" subfolder); returns (Drive file id, the
    folder's URL or ""). Raises `DealDriveFolderUploadFailed`."""
    if not DRIVE_FOLDER_ID_PATTERN.fullmatch(folder_id or "") or subfolder_name not in ALLOWED_SUBFOLDER_NAMES:
        raise DealDriveFolderUploadFailed("not a deal folder or subfolder")
    url = (os.getenv("DEAL_DRIVE_FOLDERS_UPLOAD_URL") or "").strip()
    secret = (os.getenv("DEAL_DRIVE_FOLDERS_UPLOAD_SECRET") or "").strip()
    if not url or not secret:
        raise DealDriveFolderUploadFailed("DEAL_DRIVE_FOLDERS_UPLOAD_URL and DEAL_DRIVE_FOLDERS_UPLOAD_SECRET must be set")
    if not url.startswith("https://script.google.com/"):
        raise DealDriveFolderUploadFailed("DEAL_DRIVE_FOLDERS_UPLOAD_URL must be a script.google.com web app URL")
    body = json.dumps(build_upload_request_body(folder_id=folder_id, subfolder_name=subfolder_name, file_name=file_name,
                                                file_bytes=file_bytes, secret=secret, timestamp=int(time.time())))
    request = urllib.request.Request(url, data=body.encode("utf-8"), headers={"Content-Type": "application/json"}, method="POST")
    try:
        # Apps Script answers a POST with a redirect to the result, which urllib follows as a GET.
        # nosec B310: the URL was checked above to be https://script.google.com/..., never file: or another scheme.
        with urllib.request.urlopen(request, timeout=UPLOAD_TIMEOUT_SECONDS) as response:  # nosec B310
            answer = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError) as error:
        logger.error("deal drive folder upload failed: %s", type(error).__name__)
        raise DealDriveFolderUploadFailed(type(error).__name__) from error
    if not isinstance(answer, dict) or not answer.get("ok") or not answer.get("file_id"):
        # The script's own words are for its owner's logs in Apps Script, never relayed.
        raise DealDriveFolderUploadFailed("the Drive script refused the upload")
    folder_url = str(answer.get("folder_url") or "")
    return str(answer["file_id"]), folder_url if folder_url.startswith("https://drive.google.com/") else ""
