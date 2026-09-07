"""Authentication settings, read from the environment per call.

    AUTH_MODE            off (default) | shadow | enforce
    AUTH_RP_ID           WebAuthn relying-party id: the SPA's host
                         (bigwhales.netlify.app in production, localhost in dev)
    AUTH_ORIGINS         comma-separated origins the SPA is served from
    AUTH_COOKIE_SECURE   true (default in production) | false (http dev / e2e)
    AUTH_ACCESS_MINUTES  access-token lifetime (default 15)
    AUTH_REFRESH_DAYS    refresh-token / session lifetime (default 30)
    AUTH_ENROLL_MINUTES  enrollment-link lifetime (default 15)
    AUTH_REAUTH_SECONDS  how recent a passkey assertion must be for step-up (600)
"""

from __future__ import annotations

import os

_MODES = {"off", "shadow", "enforce"}


def _env(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip()


def is_production() -> bool:
    return (_env("APP_ENV") or ("production" if os.getenv("RENDER") else "development")).lower() == "production"


def auth_mode() -> str:
    mode = _env("AUTH_MODE", "off").lower()
    return mode if mode in _MODES else "off"


def rp_id() -> str:
    return _env("AUTH_RP_ID") or ("bigwhales.netlify.app" if is_production() else "localhost")


def rp_name() -> str:
    return "Big Whales"


def allowed_origins() -> list[str]:
    raw = _env("AUTH_ORIGINS")
    if raw:
        return [o.strip().rstrip("/") for o in raw.split(",") if o.strip()]
    if is_production():
        return ["https://bigwhales.netlify.app"]
    return ["http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173"]


def cookie_secure() -> bool:
    raw = _env("AUTH_COOKIE_SECURE").lower()
    if raw in {"true", "false"}:
        return raw == "true"
    return is_production()


def cookie_name(base: str) -> str:
    # `__Host-` pins the cookie to this host over https; http (dev/e2e) cannot use it.
    return f"__Host-{base}" if cookie_secure() else base


def access_minutes() -> int:
    return _int("AUTH_ACCESS_MINUTES", 15)


def refresh_days() -> int:
    return _int("AUTH_REFRESH_DAYS", 30)


def enroll_minutes() -> int:
    return _int("AUTH_ENROLL_MINUTES", 15)


def reauth_seconds() -> int:
    return _int("AUTH_REAUTH_SECONDS", 600)


def _int(name: str, default: int) -> int:
    try:
        return max(1, int(_env(name) or default))
    except ValueError:
        return default
