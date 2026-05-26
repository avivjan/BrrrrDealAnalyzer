"""
Mercury Bank API client (multi-workspace).

Reads any environment variable matching `MERCURY_API_TOKEN` or
`MERCURY_API_TOKEN_<LABEL>` and treats each as a separate Mercury workspace.
Account balances from all workspaces are aggregated.

All amounts are returned in $k (thousands of dollars) to match the
liquidity feature's internal representation.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import requests

logger = logging.getLogger(__name__)

MERCURY_API_BASE = "https://api.mercury.com/api/v1"
MERCURY_TIMEOUT_SECONDS = 15

# Account statuses considered "live" cash that should count toward liquidity.
ACTIVE_ACCOUNT_STATUSES = {"active"}

# Env var prefix; vars like MERCURY_API_TOKEN_AJYK become workspace "AJYK".
_TOKEN_ENV_PREFIX = "MERCURY_API_TOKEN"


class MercuryConfigError(RuntimeError):
    """No Mercury tokens configured."""


class MercuryApiError(RuntimeError):
    """Mercury API returned a non-2xx response or unparseable body."""


def discover_tokens() -> dict[str, str]:
    """
    Find every Mercury token in the environment.

    Returns a dict mapping workspace label -> token. The label is the suffix
    after `MERCURY_API_TOKEN_`. An unsuffixed `MERCURY_API_TOKEN` is treated
    as workspace "default".
    """
    tokens: dict[str, str] = {}
    for key, value in os.environ.items():
        if not key.startswith(_TOKEN_ENV_PREFIX):
            continue
        token = (value or "").strip()
        if not token:
            continue
        if key == _TOKEN_ENV_PREFIX:
            label = "default"
        elif key.startswith(_TOKEN_ENV_PREFIX + "_"):
            label = key[len(_TOKEN_ENV_PREFIX) + 1:] or "default"
        else:
            continue
        tokens[label] = token
    return tokens


def _fetch_accounts_for_token(token: str) -> list[dict[str, Any]]:
    """Raw `GET /accounts` for a single workspace token."""
    url = f"{MERCURY_API_BASE}/accounts"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }
    try:
        resp = requests.get(url, headers=headers, timeout=MERCURY_TIMEOUT_SECONDS)
    except requests.RequestException as e:
        raise MercuryApiError(f"request failed: {e}") from e

    if resp.status_code in (401, 403):
        raise MercuryApiError(f"auth failed ({resp.status_code})")
    if not resp.ok:
        raise MercuryApiError(f"HTTP {resp.status_code}: {resp.text[:200]}")

    try:
        body = resp.json()
    except ValueError as e:
        raise MercuryApiError(f"non-JSON body: {e}") from e

    accounts = body.get("accounts")
    if not isinstance(accounts, list):
        raise MercuryApiError("response missing 'accounts' array")
    return accounts


def _summarize_workspace(label: str, raw_accounts: list[dict[str, Any]]) -> dict[str, Any]:
    """Convert one workspace's raw account list into our summary shape."""
    accounts: list[dict[str, Any]] = []
    total_current = 0.0
    total_available = 0.0
    counted = 0

    for acct in raw_accounts:
        status = (acct.get("status") or "").lower()
        current = float(acct.get("currentBalance") or 0.0)
        available = float(acct.get("availableBalance") or 0.0)

        include = status in ACTIVE_ACCOUNT_STATUSES
        if include:
            total_current += current
            total_available += available
            counted += 1

        accounts.append({
            "id": str(acct.get("id", "")),
            "name": str(acct.get("name") or acct.get("nickname") or ""),
            "type": str(acct.get("type") or ""),
            "status": status,
            "current_balance_k": round(current / 1000.0, 4),
            "available_balance_k": round(available / 1000.0, 4),
            "workspace": label,
        })

    return {
        "workspace": label,
        "total_balance_k": round(total_current / 1000.0, 4),
        "total_available_k": round(total_available / 1000.0, 4),
        "account_count": counted,
        "accounts": accounts,
    }


def summarize_balance() -> dict[str, Any]:
    """
    Fetch every configured Mercury workspace and return an aggregated summary.

    Returns:
        {
            "total_balance_k": float,        # sum across all successful workspaces, in $k
            "total_available_k": float,
            "account_count": int,
            "workspace_count": int,          # number of workspaces that succeeded
            "workspaces": [                  # per-workspace breakdown (successes)
                {
                    "workspace": "AJYK",
                    "total_balance_k": ...,
                    "total_available_k": ...,
                    "account_count": ...,
                    "accounts": [...],
                },
                ...
            ],
            "workspace_errors": [            # per-workspace failures (if any)
                {"workspace": "AY", "error": "auth failed (401)"},
                ...
            ],
            "accounts": [...],               # flat list across all successful workspaces
        }

    Raises:
        MercuryConfigError: no tokens found in environment.
        MercuryApiError: every configured workspace failed.
    """
    tokens = discover_tokens()
    if not tokens:
        raise MercuryConfigError(
            "No Mercury tokens found. Add MERCURY_API_TOKEN_<LABEL> entries "
            "(e.g. MERCURY_API_TOKEN_AJYK, MERCURY_API_TOKEN_AY) to BackEnd/.env."
        )

    workspaces: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    flat_accounts: list[dict[str, Any]] = []
    total_current = 0.0
    total_available = 0.0
    counted = 0

    for label in sorted(tokens.keys()):
        try:
            raw = _fetch_accounts_for_token(tokens[label])
        except MercuryApiError as e:
            logger.warning("Mercury workspace %s failed: %s", label, e)
            errors.append({"workspace": label, "error": str(e)})
            continue

        ws = _summarize_workspace(label, raw)
        workspaces.append(ws)
        flat_accounts.extend(ws["accounts"])
        total_current += ws["total_balance_k"]
        total_available += ws["total_available_k"]
        counted += ws["account_count"]

    if not workspaces and errors:
        # Every workspace failed; surface as a single API error so the
        # endpoint can return 502.
        joined = "; ".join(f"{e['workspace']}: {e['error']}" for e in errors)
        raise MercuryApiError(joined)

    return {
        "total_balance_k": round(total_current, 4),
        "total_available_k": round(total_available, 4),
        "account_count": counted,
        "workspace_count": len(workspaces),
        "workspaces": workspaces,
        "workspace_errors": errors,
        "accounts": flat_accounts,
    }


# Kept for backwards compatibility with any external callers.
def fetch_accounts() -> list[dict[str, Any]]:
    """Flat list of accounts across all workspaces (no workspace tagging)."""
    return summarize_balance()["accounts"]
