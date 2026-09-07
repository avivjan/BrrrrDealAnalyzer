"""Phase 0 stopgap: a single shared key in front of every data route.

This is NOT the target authentication (see SECURITY_PLAN.md §3.2 -- passkeys
and sessions replace it in Phase 2). It exists so the API stops being open to
the whole internet while that work happens.

    APP_KEY_MODE   off      (default) nothing is checked -- today's behaviour
                   shadow   a missing/wrong key is logged, the request goes on
                   enforce  a missing/wrong key is a 401
    APP_KEY        the shared secret the browser sends as `X-App-Key`

Both are read per request so a test can flip them with monkeypatch and Render
can flip them without a code deploy. The dependency reads the header from the
raw request instead of declaring a `Header()` parameter, so it adds nothing to
the OpenAPI document and the regression snapshot stays byte-identical.
"""

from __future__ import annotations

import hmac
import logging
import os

from fastapi import HTTPException, Request

logger = logging.getLogger(__name__)

HEADER = "X-App-Key"
DETAIL = "app_key_required"
_MODES = {"off", "shadow", "enforce"}


def app_key_mode() -> str:
    mode = (os.getenv("APP_KEY_MODE") or "off").strip().lower()
    return mode if mode in _MODES else "off"


def configured_key() -> str:
    return (os.getenv("APP_KEY") or "").strip()


def key_matches(presented: str | None) -> bool:
    expected = configured_key()
    if not expected or not presented:
        return False
    return hmac.compare_digest(presented.strip().encode(), expected.encode())


async def require_app_key(request: Request) -> None:
    mode = app_key_mode()
    if mode == "off":
        return
    if key_matches(request.headers.get(HEADER)):
        return
    if mode == "shadow":
        logger.warning(
            "app key shadow: would reject %s %s from %s",
            request.method,
            request.url.path,
            request.client.host if request.client else "?",
        )
        return
    raise HTTPException(status_code=401, detail=DETAIL)
