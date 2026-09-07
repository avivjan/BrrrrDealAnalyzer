"""Reject request bodies larger than MAX_BODY_BYTES before they are read.

A pure ASGI middleware: it looks at `Content-Length` (the REPS batch upload is
the only large payload the site sends; 30 MB leaves room for it, and the
Netlify proxy in front of the API caps bodies at 25 MB anyway). A body without
a declared length is left to the upload caps in the REPS router.
"""

from __future__ import annotations

import json
import os

DEFAULT_MAX_BODY_BYTES = 30 * 1024 * 1024


def max_body_bytes() -> int:
    raw = (os.getenv("MAX_BODY_BYTES") or "").strip()
    try:
        return int(raw) if raw else DEFAULT_MAX_BODY_BYTES
    except ValueError:
        return DEFAULT_MAX_BODY_BYTES


class BodyLimitMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            for name, value in scope.get("headers") or []:
                if name == b"content-length":
                    try:
                        length = int(value)
                    except ValueError:
                        length = -1
                    if length > max_body_bytes():
                        body = json.dumps({"detail": "request body too large"}).encode()
                        await send({
                            "type": "http.response.start",
                            "status": 413,
                            "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())],
                        })
                        await send({"type": "http.response.body", "body": body})
                        return
                    break
        await self.app(scope, receive, send)
