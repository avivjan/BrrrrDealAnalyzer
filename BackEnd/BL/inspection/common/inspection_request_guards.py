"""Abuse protection for the public inspection endpoints.

Rate limits: an in-memory sliding window per client IP and per limit name.
The other limits in this app count rows of `audit_log`, but the inspection
autosave makes a request on almost every tap; writing an audit row for each
would fill that table. The API runs as one process on Render, so a
per-process window is enough, and a restart only resets the counts.

Writes also need the same CSRF signals as the session gate (an allowed
`Origin`, no cross-site `Sec-Fetch-Site`, and the `X-Requested-With`
header), so another website cannot fill an inspection from a visitor's browser.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from typing import Callable, Deque, Dict, Tuple

from fastapi import HTTPException, Request

from BL.auth.common.audit import client_ip
from BL.auth.common.session_dependency import _csrf_problem

SECONDS_PER_HOUR = 3600
MAXIMUM_JSON_BODY_BYTES = 32 * 1024
MAXIMUM_TRACKED_LIMIT_AND_IP_PAIRS = 10_000

# Requests allowed per client IP per hour.
REQUESTS_PER_HOUR_BY_LIMIT_NAME: Dict[str, int] = {
    "inspection_create": 20,
    "inspection_read": 1200,
    "inspection_start_info_update": 600,
    "inspection_item_update": 1200,
    "inspection_complete": 60,
    "inspection_photo_upload": 300,
    "inspection_photo_read": 3000,
    "inspection_photo_delete": 300,
}

_request_times_by_limit_and_ip: Dict[Tuple[str, str], Deque[float]] = {}
_request_times_lock = threading.Lock()


def reset_inspection_rate_limits() -> None:
    """Tests start every case with empty windows."""

    with _request_times_lock:
        _request_times_by_limit_and_ip.clear()


def _within_rate_limit(limit_name: str, ip_address: str) -> bool:
    now = time.monotonic()
    allowed_requests = REQUESTS_PER_HOUR_BY_LIMIT_NAME[limit_name]
    with _request_times_lock:
        if len(_request_times_by_limit_and_ip) > MAXIMUM_TRACKED_LIMIT_AND_IP_PAIRS:
            for stale_key in [key for key, times in _request_times_by_limit_and_ip.items() if not times or now - times[-1] > SECONDS_PER_HOUR]:
                del _request_times_by_limit_and_ip[stale_key]
        request_times = _request_times_by_limit_and_ip.setdefault((limit_name, ip_address), deque())
        while request_times and now - request_times[0] > SECONDS_PER_HOUR:
            request_times.popleft()
        if len(request_times) >= allowed_requests:
            return False
        request_times.append(now)
        return True


def inspection_request_guard(limit_name: str, *, is_json_write: bool = False) -> Callable[[Request], None]:
    """A FastAPI dependency: rate limit, then (for writes) CSRF and a body size cap."""

    if limit_name not in REQUESTS_PER_HOUR_BY_LIMIT_NAME:
        raise ValueError(f"unknown inspection rate limit {limit_name!r}")

    def guard(request: Request) -> None:
        if not _within_rate_limit(limit_name, client_ip(request) or "unknown"):
            raise HTTPException(status_code=429, detail="Too many requests. Please wait a few minutes and try again.")
        csrf_problem = _csrf_problem(request)
        if csrf_problem is not None:
            raise HTTPException(status_code=403, detail=csrf_problem)
        if is_json_write:
            declared_length = request.headers.get("content-length")
            if declared_length is None or not declared_length.isdigit() or int(declared_length) > MAXIMUM_JSON_BODY_BYTES:
                raise HTTPException(status_code=413, detail="request body too large")

    return guard
