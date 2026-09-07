"""Log filters that keep secrets out of the log stream.

`MCPPathRedactFilter` rewrites the request path in uvicorn's access-log records
so `/mcp/<MCP_PATH_SECRET>` is written as `/mcp/[redacted]`. Uvicorn formats
the access line from `record.args = (client, method, path, version, status)`,
so the path is replaced in place before the message is rendered. Render's own
HTTP-layer logs are outside this process; rotate the secret if those were ever
shared.
"""

from __future__ import annotations

import logging
import re

_MCP_PATH = re.compile(r"(/mcp/)[^\s?/]+")


def redact_mcp_path(text: str) -> str:
    return _MCP_PATH.sub(r"\1[redacted]", text)


class MCPPathRedactFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:  # noqa: D401 - logging API
        if isinstance(record.args, tuple) and record.args:
            record.args = tuple(
                redact_mcp_path(a) if isinstance(a, str) else a for a in record.args
            )
        if isinstance(record.msg, str) and "/mcp/" in record.msg:
            record.msg = redact_mcp_path(record.msg)
        return True


def install_access_log_redaction() -> None:
    logging.getLogger("uvicorn.access").addFilter(MCPPathRedactFilter())


# --- Secret values -------------------------------------------------------- #

# Environment variables whose values must never appear in a log line.
SECRET_ENV_VARS = ("EMAIL_PASSWORD", "APP_KEY", "MCP_PATH_SECRET", "DATABASE_URL")
_SECRET_ENV_PREFIXES = ("MERCURY_API_TOKEN",)
_BEARER = re.compile(r"(Bearer\s+)[A-Za-z0-9._~+/=-]+")


def _secret_values() -> list[str]:
    import os

    values = [os.getenv(k) or "" for k in SECRET_ENV_VARS]
    values += [v for k, v in os.environ.items() if k.startswith(_SECRET_ENV_PREFIXES)]
    return [v for v in values if len(v) >= 8]


def redact_secrets(text: str) -> str:
    text = _BEARER.sub(r"\1[REDACTED]", text)
    for value in _secret_values():
        if value in text:
            text = text.replace(value, "[REDACTED]")
    return text


class SecretRedactFilter(logging.Filter):
    """Replaces configured secret values and bearer tokens in every record.

    The values are read per record so a rotation takes effect without a
    restart; the check is a substring scan over a handful of strings.
    """

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: D401
        try:
            message = record.getMessage()
        except Exception:  # noqa: BLE001
            return True
        redacted = redact_secrets(message)
        if redacted != message:
            record.msg = redacted
            record.args = ()
        return True


def install_secret_redaction() -> None:
    root = logging.getLogger()
    if not any(isinstance(f, SecretRedactFilter) for f in root.filters):
        root.addFilter(SecretRedactFilter())
    # Filters on the root logger do not apply to records emitted by child
    # loggers, so attach to the handlers `basicConfig` installed as well.
    for handler in root.handlers:
        if not any(isinstance(f, SecretRedactFilter) for f in handler.filters):
            handler.addFilter(SecretRedactFilter())
