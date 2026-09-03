"""Single-file convenience shim -- kept for backward compatibility.

New clients should call `/reps/upload-batch`.

Raises `reps_service.RepsConfigError` / `RepsValidationError` on failure; any
other exception propagates too -- the router maps all three to HTTP responses.
"""

from typing import Optional

from BL.reps.common import reps_service


def upload_single(*, user: str, file_bytes: bytes, filename: str, content_type: Optional[str]) -> str:
    return reps_service.upload_evidence(
        user=user,
        file_bytes=file_bytes,
        original_filename=filename,
        content_type=content_type,
    )
