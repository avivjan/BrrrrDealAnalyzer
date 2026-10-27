"""Saves signed copies into the company's Google Drive folder "loan agreements".

A service account cannot keep files in a personal Gmail account's Drive (it has
no storage quota), so the upload goes through a small Google Apps Script web
app owned by bigwhalesllc@gmail.com (`BackEnd/integrations/google_drive_loan_agreements.gs`).
The script creates the folder if needed and saves the PDF there.

Every request is signed: HMAC-SHA256 with the shared secret over
"<timestamp>\\n<file name>\\n<SHA-256 of the PDF>". The script refuses a wrong
signature, a PDF whose SHA-256 differs, and a timestamp more than 5 minutes
old, so the web app's URL alone lets nobody write to the Drive.

    MEMBER_LOAN_DRIVE_UPLOAD_URL     the Apps Script web app URL (…/exec)
    MEMBER_LOAN_DRIVE_UPLOAD_SECRET  the shared secret, also stored in the script's properties

Both come from the environment only. Tests replace `save_pdf_to_loan_agreements_folder`.
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

LOAN_AGREEMENTS_FOLDER_NAME = "loan agreements"
UPLOAD_TIMEOUT_SECONDS = 60


class MemberLoanDriveUploadFailed(Exception):
    pass


def upload_signature(secret: str, timestamp: int, file_name: str, pdf_sha256: str) -> str:
    message = f"{timestamp}\n{file_name}\n{pdf_sha256}".encode("utf-8")
    return hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()


def build_upload_request_body(*, file_name: str, pdf: bytes, secret: str, timestamp: int) -> dict:
    pdf_sha256 = hashlib.sha256(pdf).hexdigest()
    return {
        "folder_name": LOAN_AGREEMENTS_FOLDER_NAME,
        "file_name": file_name,
        "pdf_base64": base64.b64encode(pdf).decode("ascii"),
        "pdf_sha256": pdf_sha256,
        "timestamp": timestamp,
        "signature": upload_signature(secret, timestamp, file_name, pdf_sha256),
    }


def save_pdf_to_loan_agreements_folder(file_name: str, pdf: bytes) -> str:
    """Upload and return the Drive file id. Raises `MemberLoanDriveUploadFailed`."""

    url = (os.getenv("MEMBER_LOAN_DRIVE_UPLOAD_URL") or "").strip()
    secret = (os.getenv("MEMBER_LOAN_DRIVE_UPLOAD_SECRET") or "").strip()
    if not url or not secret:
        raise MemberLoanDriveUploadFailed("MEMBER_LOAN_DRIVE_UPLOAD_URL and MEMBER_LOAN_DRIVE_UPLOAD_SECRET must be set")
    if not url.startswith("https://script.google.com/"):
        raise MemberLoanDriveUploadFailed("MEMBER_LOAN_DRIVE_UPLOAD_URL must be a script.google.com web app URL")
    body = json.dumps(build_upload_request_body(file_name=file_name, pdf=pdf, secret=secret, timestamp=int(time.time())))
    request = urllib.request.Request(url, data=body.encode("utf-8"), headers={"Content-Type": "application/json"}, method="POST")
    try:
        # Apps Script answers a POST with a redirect to the result, which urllib follows as a GET.
        with urllib.request.urlopen(request, timeout=UPLOAD_TIMEOUT_SECONDS) as response:
            answer = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError) as error:
        logger.error("member loan drive upload failed: %s", type(error).__name__)
        raise MemberLoanDriveUploadFailed(type(error).__name__) from error
    if not isinstance(answer, dict) or not answer.get("ok") or not answer.get("file_id"):
        reason = str(answer.get("error") if isinstance(answer, dict) else "unexpected answer")[:200]
        raise MemberLoanDriveUploadFailed(f"the Drive script refused the upload: {reason}")
    return str(answer["file_id"])
