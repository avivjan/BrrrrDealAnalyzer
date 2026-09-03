"""Upload one or many evidence files into a per-log GCS sub-folder.

The folder + per-file URLs are returned to the frontend, which then sends
them back inside the `/reps/log` payload so the Sheet stores both the
folder URL (auditor's index page) and each file URL.

Raises `reps_service.RepsConfigError` / `RepsValidationError` on failure; any
other exception propagates too -- the router maps all three to HTTP responses.
"""

from datetime import datetime
from typing import List, Optional, Tuple

from ReqRes.common.reps_schemas import RepsUploadBatchRes, RepsUploadedFile
from BL.reps.common import reps_service


def upload_batch(
    *,
    user: str,
    property_name: Optional[str],
    activity_category: Optional[str],
    log_timestamp: Optional[datetime],
    items: List[Tuple[str, Optional[str], bytes]],
) -> RepsUploadBatchRes:
    batch = reps_service.upload_evidence_batch(
        user=user,
        property_name=property_name,
        activity_category=activity_category,
        log_timestamp=log_timestamp,
        items=items,
    )
    return RepsUploadBatchRes(
        folder_url=batch.folder_url,
        folder_path=batch.folder_path,
        files=[
            RepsUploadedFile(
                name=a.name,
                url=a.url,
                content_type=a.content_type,
                size_bytes=a.size_bytes,
            )
            for a in batch.files
        ],
    )
