"""
Mercury Bank API client.

Fetches account balances from https://api.mercury.com/api/v1/accounts.
Auth: Bearer token from the MERCURY_API_TOKEN environment variable.

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


class MercuryConfigError(RuntimeError):
    """MERCURY_API_TOKEN is missing or empty."""


class MercuryApiError(RuntimeError):
    """Mercury API returned a non-2xx response or unparseable body."""


def _get_token() -> str:
    token = os.getenv("MERCURY_API_TOKEN", "").strip()
    if not token:
        raise MercuryConfigError(
            "MERCURY_API_TOKEN is not set. Add it to BackEnd/.env to enable Mercury sync."
        )
    return token


def fetch_accounts() -> list[dict[str, Any]]:
    """
    Return the raw list of account dicts from Mercury.

    Each item includes fields like: id, name, type, status,
    currentBalance, availableBalance, accountNumber, routingNumber.
    """
    token = _get_token()
    url = f"{MERCURY_API_BASE}/accounts"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }
    try:
        resp = requests.get(url, headers=headers, timeout=MERCURY_TIMEOUT_SECONDS)
    except requests.RequestException as e:
        raise MercuryApiError(f"Mercury request failed: {e}") from e

    if resp.status_code == 401 or resp.status_code == 403:
        raise MercuryApiError(
            f"Mercury auth failed ({resp.status_code}). Check MERCURY_API_TOKEN."
        )
    if not resp.ok:
        raise MercuryApiError(
            f"Mercury API returned {resp.status_code}: {resp.text[:200]}"
        )

    try:
        body = resp.json()
    except ValueError as e:
        raise MercuryApiError(f"Mercury returned non-JSON body: {e}") from e

    accounts = body.get("accounts")
    if not isinstance(accounts, list):
        raise MercuryApiError("Mercury response missing 'accounts' array")
    return accounts


def summarize_balance() -> dict[str, Any]:
    """
    Fetch all Mercury accounts and return a summary.

    Returns:
        {
            "total_balance_k": float,        # sum of currentBalance for active accounts, in $k
            "total_available_k": float,      # same, using availableBalance
            "account_count": int,            # number of active accounts counted
            "accounts": [
                {
                    "id": str,
                    "name": str,
                    "type": str,
                    "status": str,
                    "current_balance_k": float,
                    "available_balance_k": float,
                },
                ...
            ],
        }
    """
    raw = fetch_accounts()

    summary_accounts: list[dict[str, Any]] = []
    total_current = 0.0
    total_available = 0.0
    counted = 0

    for acct in raw:
        status = (acct.get("status") or "").lower()
        current = float(acct.get("currentBalance") or 0.0)
        available = float(acct.get("availableBalance") or 0.0)

        include = status in ACTIVE_ACCOUNT_STATUSES
        if include:
            total_current += current
            total_available += available
            counted += 1

        summary_accounts.append({
            "id": str(acct.get("id", "")),
            "name": str(acct.get("name") or acct.get("nickname") or ""),
            "type": str(acct.get("type") or ""),
            "status": status,
            "current_balance_k": round(current / 1000.0, 4),
            "available_balance_k": round(available / 1000.0, 4),
        })

    return {
        "total_balance_k": round(total_current / 1000.0, 4),
        "total_available_k": round(total_available / 1000.0, 4),
        "account_count": counted,
        "accounts": summary_accounts,
    }
