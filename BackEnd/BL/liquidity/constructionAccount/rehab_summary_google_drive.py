"""Saves each rehab summary (its PDF and its CSV) into the owner's Google Drive, under "rehab summaries/<one folder per
deal>" (tasks/todo/ConstructionAccountsCompactCardsAndRehabSummary.md).

A service account cannot keep files in a personal Gmail Drive (it has no storage quota), so the upload goes through a
small Google Apps Script web app owned by the owner's personal Google account
(`BackEnd/integrations/google_drive_rehab_summaries.gs`).

Every request is signed: HMAC-SHA256 with the shared secret over
"<timestamp>\\n<folder name>/<file name>\\n<SHA-256 of the file>". The script refuses a wrong signature, a file whose
SHA-256 differs, a timestamp more than 5 minutes old, and any file but a .pdf or a .csv, and writes only inside its
"rehab summaries" folder, so the web app's URL alone lets nobody write to the Drive.

    REHAB_SUMMARY_DRIVE_UPLOAD_URL     the Apps Script web app URL (…/exec)
    REHAB_SUMMARY_DRIVE_UPLOAD_SECRET  the shared secret, also stored in the script's properties

Both come from the environment only. Tests replace `save_rehab_summary_file_to_drive` in the delivery module.
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

logger = logging.getLogger(__name__)

UPLOAD_TIMEOUT_SECONDS = 60
FOLDER_NAME_UNSAFE_CHARACTERS_PATTERN = re.compile(r"[^A-Za-z0-9 ,.#()_-]+")
LARGEST_FOLDER_NAME_LENGTH = 160


class RehabSummaryDriveUploadFailed(Exception):
    pass


def rehab_summary_drive_folder_name(deal_address: str, bought_deal_id: str) -> str:
    """One folder per deal: its address (made safe) and its id, so two deals at one address never share a folder."""
    safe_address = FOLDER_NAME_UNSAFE_CHARACTERS_PATTERN.sub(" ", deal_address).strip() or "rehab"
    return f"{safe_address[:LARGEST_FOLDER_NAME_LENGTH - 40].strip()} ({bought_deal_id})"


def upload_signature(secret: str, timestamp: int, subject: str, file_sha256: str) -> str:
    message = f"{timestamp}\n{subject}\n{file_sha256}".encode("utf-8")
    return hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()


def build_upload_request_body(*, folder_name: str, file_name: str, file_bytes: bytes, secret: str, timestamp: int) -> dict:
    file_sha256 = hashlib.sha256(file_bytes).hexdigest()
    subject = f"{folder_name}/{file_name}"
    return {
        "folder_name": folder_name,
        "file_name": file_name,
        "file_base64": base64.b64encode(file_bytes).decode("ascii"),
        "file_sha256": file_sha256,
        "timestamp": timestamp,
        "signature": upload_signature(secret, timestamp, subject, file_sha256),
    }


def save_rehab_summary_file_to_drive(folder_name: str, file_name: str, file_bytes: bytes) -> tuple[str, str]:
    """Upload one .pdf or .csv; returns (Drive file id, folder URL or ""). Raises `RehabSummaryDriveUploadFailed`."""

    url = (os.getenv("REHAB_SUMMARY_DRIVE_UPLOAD_URL") or "").strip()
    secret = (os.getenv("REHAB_SUMMARY_DRIVE_UPLOAD_SECRET") or "").strip()
    if not url or not secret:
        raise RehabSummaryDriveUploadFailed("REHAB_SUMMARY_DRIVE_UPLOAD_URL and REHAB_SUMMARY_DRIVE_UPLOAD_SECRET must be set")
    if not url.startswith("https://script.google.com/"):
        raise RehabSummaryDriveUploadFailed("REHAB_SUMMARY_DRIVE_UPLOAD_URL must be a script.google.com web app URL")
    body = json.dumps(build_upload_request_body(folder_name=folder_name, file_name=file_name, file_bytes=file_bytes,
                                                secret=secret, timestamp=int(time.time())))
    request = urllib.request.Request(url, data=body.encode("utf-8"), headers={"Content-Type": "application/json"}, method="POST")
    try:
        # Apps Script answers a POST with a redirect to the result, which urllib follows as a GET.
        # nosec B310: the URL was checked above to be https://script.google.com/..., never file: or another scheme.
        with urllib.request.urlopen(request, timeout=UPLOAD_TIMEOUT_SECONDS) as response:  # nosec B310
            answer = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError) as error:
        logger.error("rehab summary drive upload failed: %s", type(error).__name__)
        raise RehabSummaryDriveUploadFailed(type(error).__name__) from error
    if not isinstance(answer, dict) or not answer.get("ok") or not answer.get("file_id"):
        raise RehabSummaryDriveUploadFailed("the Drive script refused the upload")
    folder_url = str(answer.get("folder_url") or "")
    return str(answer["file_id"]), folder_url if folder_url.startswith("https://drive.google.com/") else ""
