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
