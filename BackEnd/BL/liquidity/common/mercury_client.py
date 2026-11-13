"""
Mercury Bank API client (multi-workspace).

Reads any environment variable matching `MERCURY_API_TOKEN` or
`MERCURY_API_TOKEN_<LABEL>` and treats each as a separate Mercury workspace.
Account balances from all workspaces are aggregated.

All amounts are returned in exact dollars, rounded to the cent, like the
rest of the liquidity feature.
"""

from __future__ import annotations

import logging
import os
import re
import time
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

import requests

from BL.common.secret import Secret

logger = logging.getLogger(__name__)

MERCURY_API_BASE = "https://api.mercury.com/api/v1"
MERCURY_TIMEOUT_SECONDS = 15

# Account statuses considered "live" cash that should count toward liquidity.
ACTIVE_ACCOUNT_STATUSES = {"active"}

# Env var prefix; vars like MERCURY_API_TOKEN_AJYK become workspace "AJYK".
_TOKEN_ENV_PREFIX = "MERCURY_API_TOKEN"

# The only Mercury endpoints this module ever calls, both read-only: the accounts, and one account's
# transactions (a rehab's construction account, tasks/todo/ConstructionAccountPerRehab.md). Tokens are
# read-only and IP-allow-listed on the Mercury side (SECURITY_PLAN.md §3.3); the code side of that
# promise is that nothing else is requested (tests pin this).
ACCOUNTS_URL = f"{MERCURY_API_BASE}/accounts"

# An account id goes into the transactions URL: only this shape is ever put there.
_MERCURY_ID_PATTERN = re.compile(r"[A-Za-z0-9-]{1,80}")
TRANSACTIONS_PAGE_SIZE = 500
# A construction account lives for one rehab: far fewer rows than this. The cap bounds a runaway loop.
MAX_TRANSACTION_PAGES = 20
# Mercury lists only recent transactions unless a start date is given.
EARLIEST_TRANSACTION_DATE = "2015-01-01"
INTERNAL_TRANSFER_KIND = "internalTransfer"
FAILED_OR_CANCELLED_TRANSACTION_STATUSES = {"failed", "cancelled"}
PENDING_TRANSACTION_STATUS = "pending"
_transactions_cache: dict[tuple[str, str], tuple[float, list[dict[str, Any]]]] = {}

# A successful summary is reused for this long so a page reload, or a run of
# MCP calls, does not fan out to Mercury every time.
DEFAULT_CACHE_SECONDS = 60
_cache: tuple[float, dict[str, Any]] | None = None


class MercuryConfigError(RuntimeError):
    """No Mercury tokens configured."""


class MercuryApiError(RuntimeError):
    """Mercury API returned a non-2xx response or unparseable body."""


class MercurySlowDownError(MercuryApiError):
    """Mercury answered 429: too many requests. `retry_after_seconds` is its Retry-After header, when it sent a usable one."""

    def __init__(self, retry_after_seconds: int | None = None):
        super().__init__("Mercury asked us to slow down (429)")
        self.retry_after_seconds = retry_after_seconds


def _raise_for_an_error_status(resp) -> None:
    """Our own words for a refused request: upstream bodies are third-party text and are never relayed."""
    if resp.status_code == 429:
        try:
            retry_after_seconds = int((getattr(resp, "headers", None) or {}).get("Retry-After", ""))
        except (TypeError, ValueError):
            retry_after_seconds = None
        raise MercurySlowDownError(retry_after_seconds if retry_after_seconds and retry_after_seconds > 0 else None)
    if resp.status_code in (401, 403):
        raise MercuryApiError(f"auth failed ({resp.status_code})")
    if not resp.ok:
        raise MercuryApiError(f"HTTP {resp.status_code}")


def discover_tokens() -> dict[str, Secret]:
    """
    Find every Mercury token in the environment.

    Returns a dict mapping workspace label -> `Secret`. The label is the suffix
    after `MERCURY_API_TOKEN_`. An unsuffixed `MERCURY_API_TOKEN` is treated
    as workspace "default". The values print as `Secret(***)`; only
    `_fetch_accounts_for_token` reveals them, into the Authorization header.
    """
    tokens: dict[str, Secret] = {}
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
        tokens[label] = Secret(token)
    return tokens


def _fetch_accounts_for_token(token: Secret) -> list[dict[str, Any]]:
    """Raw `GET /accounts` for a single workspace token."""
    headers = {
        "Authorization": f"Bearer {token.reveal()}",
        "Accept": "application/json",
    }
    try:
        resp = requests.get(ACCOUNTS_URL, headers=headers, timeout=MERCURY_TIMEOUT_SECONDS)
    except requests.RequestException as e:
        # The exception text can embed the request (and so the header); log
        # the class only and keep the client-facing message generic.
        logger.warning("Mercury request failed: %s", type(e).__name__)
        raise MercuryApiError("request failed") from e

    _raise_for_an_error_status(resp)

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
            # Enough to tell two accounts apart on screen; the full number never leaves this module.
            "account_number_last_four": str(acct.get("accountNumber") or "")[-4:],
            "name": str(acct.get("name") or acct.get("nickname") or ""),
            "type": str(acct.get("type") or ""),
            "status": status,
            "current_balance_dollars": round(current, 2),
            "available_balance_dollars": round(available, 2),
            "workspace": label,
        })

    return {
        "workspace": label,
        "total_balance_dollars": round(total_current, 2),
        "total_available_dollars": round(total_available, 2),
        "account_count": counted,
        "accounts": accounts,
    }


def fetch_workspace_summary(workspace_label: str) -> dict[str, Any]:
    """One workspace's accounts, read from Mercury now (never cached here) and summarised like a `workspaces` entry of
    `summarize_balance`. Raises `MercuryConfigError` (no token for that workspace), `MercurySlowDownError` or `MercuryApiError`."""
    token = discover_tokens().get(workspace_label)
    if token is None:
        raise MercuryConfigError("No Mercury token for that workspace")
    try:
        return _summarize_workspace(workspace_label, _fetch_accounts_for_token(token))
    finally:
        token.wipe()


def combine_workspace_summaries(workspaces: list[dict[str, Any]], errors: list[dict[str, str]]) -> dict[str, Any]:
    """The `summarize_balance` shape from per-workspace summaries and per-workspace failures."""
    return {
        "total_balance_dollars": round(sum(workspace["total_balance_dollars"] for workspace in workspaces), 2),
        "total_available_dollars": round(sum(workspace["total_available_dollars"] for workspace in workspaces), 2),
        "account_count": sum(workspace["account_count"] for workspace in workspaces),
        "workspace_count": len(workspaces),
        "workspaces": workspaces,
        "workspace_errors": errors,
        "accounts": [account for workspace in workspaces for account in workspace["accounts"]],
    }


def cache_seconds() -> int:
    raw = (os.getenv("MERCURY_CACHE_SECONDS") or "").strip()
    try:
        return max(0, int(raw)) if raw else DEFAULT_CACHE_SECONDS
    except ValueError:
        return DEFAULT_CACHE_SECONDS


def clear_cache() -> None:
    global _cache
    _cache = None
    _transactions_cache.clear()


def account_transactions_url(account_id: str) -> str:
    if not _MERCURY_ID_PATTERN.fullmatch(account_id or ""):
        raise MercuryApiError("invalid account id")
    return f"{MERCURY_API_BASE}/account/{account_id}/transactions"


def _transaction_date_of(raw_transaction: dict[str, Any]) -> date | None:
    for key in ("postedAt", "createdAt"):
        try:
            return date.fromisoformat(str(raw_transaction.get(key) or "")[:10])
        except ValueError:
            continue
    return None


def _normalised_transaction(raw_transaction: dict[str, Any]) -> dict[str, Any]:
    try:
        signed_amount_dollars = Decimal(str(raw_transaction.get("amount") or 0)).quantize(Decimal("0.01"))
    except InvalidOperation as e:
        raise MercuryApiError("transaction without a numeric amount") from e
    status = str(raw_transaction.get("status") or "").lower()
    return {
        "id": str(raw_transaction.get("id", "")),
        "signed_amount_dollars": signed_amount_dollars,   # positive = into the account
        "kind": str(raw_transaction.get("kind") or ""),
        "status": status,
        "counterparty_name": str(raw_transaction.get("counterpartyNickname") or raw_transaction.get("counterpartyName")
                                 or raw_transaction.get("bankDescription") or "")[:200],
        "transaction_date": _transaction_date_of(raw_transaction),
        "is_internal_transfer": str(raw_transaction.get("kind") or "") == INTERNAL_TRANSFER_KIND,
        "is_failed_or_cancelled": status in FAILED_OR_CANCELLED_TRANSACTION_STATUSES,
        "is_pending": status == PENDING_TRANSACTION_STATUS,
    }


def fetch_account_transactions(workspace_label: str, account_id: str, use_cache: bool = True) -> list[dict[str, Any]]:
    """Every transaction of one account, oldest first, with the workspace's read-only token. Cached like the balances;
    `use_cache=False` always reads Mercury (and still leaves the fresh list in the cache).

    Raises `MercuryConfigError` (no token for that workspace), `MercurySlowDownError` or `MercuryApiError`.
    """
    url = account_transactions_url(account_id)
    cache_key = (workspace_label, account_id)
    ttl = cache_seconds()
    cached = _transactions_cache.get(cache_key)
    if use_cache and cached is not None and ttl > 0 and time.monotonic() - cached[0] < ttl:
        return cached[1]
    token = discover_tokens().get(workspace_label)
    if token is None:
        raise MercuryConfigError("No Mercury token for that workspace")
    headers = {"Authorization": f"Bearer {token.reveal()}", "Accept": "application/json"}
    transactions: list[dict[str, Any]] = []
    try:
        for page_number in range(MAX_TRANSACTION_PAGES):
            params = {"limit": TRANSACTIONS_PAGE_SIZE, "offset": page_number * TRANSACTIONS_PAGE_SIZE,
                      "start": EARLIEST_TRANSACTION_DATE, "order": "asc"}
            try:
                resp = requests.get(url, headers=headers, params=params, timeout=MERCURY_TIMEOUT_SECONDS)
            except requests.RequestException as e:
                logger.warning("Mercury request failed: %s", type(e).__name__)
                raise MercuryApiError("request failed") from e
            _raise_for_an_error_status(resp)
            try:
                page = resp.json().get("transactions")
            except (ValueError, AttributeError) as e:
                raise MercuryApiError("non-JSON body") from e
            if not isinstance(page, list):
                raise MercuryApiError("response missing 'transactions' array")
            transactions.extend(_normalised_transaction(raw_transaction) for raw_transaction in page)
            if len(page) < TRANSACTIONS_PAGE_SIZE:
                break
        else:
            raise MercuryApiError("too many transactions")
    finally:
        token.wipe()
    transactions.sort(key=lambda transaction: (transaction["transaction_date"] or date.max, transaction["id"]))
    _transactions_cache[cache_key] = (time.monotonic(), transactions)
    return transactions


def summarize_balance() -> dict[str, Any]:
    """
    Fetch every configured Mercury workspace and return an aggregated summary.

    A fully or partly successful summary is cached for `cache_seconds()`; the
    "no tokens configured" and "every workspace failed" errors are never cached.

    Returns:
        {
            "total_balance_dollars": float,        # sum across all successful workspaces, in dollars
            "total_available_dollars": float,
            "account_count": int,
            "workspace_count": int,          # number of workspaces that succeeded
            "workspaces": [                  # per-workspace breakdown (successes)
                {
                    "workspace": "AJYK",
                    "total_balance_dollars": ...,
                    "total_available_dollars": ...,
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
    global _cache
    tokens = discover_tokens()
    if not tokens:
        raise MercuryConfigError(
            "No Mercury tokens found. Add MERCURY_API_TOKEN_<LABEL> entries "
            "(e.g. MERCURY_API_TOKEN_AJYK, MERCURY_API_TOKEN_AY) to BackEnd/.env."
        )

    ttl = cache_seconds()
    if _cache is not None and ttl > 0 and time.monotonic() - _cache[0] < ttl:
        return _cache[1]

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
        total_current += ws["total_balance_dollars"]
        total_available += ws["total_available_dollars"]
        counted += ws["account_count"]

    if not workspaces and errors:
        # Every workspace failed; surface as a single API error so the
        # endpoint can return 502.
        joined = "; ".join(f"{e['workspace']}: {e['error']}" for e in errors)
        raise MercuryApiError(joined)

    result = {
        "total_balance_dollars": round(total_current, 2),
        "total_available_dollars": round(total_available, 2),
        "account_count": counted,
        "workspace_count": len(workspaces),
        "workspaces": workspaces,
        "workspace_errors": errors,
        "accounts": flat_accounts,
    }
    for secret in tokens.values():
        secret.wipe()
    _cache = (time.monotonic(), result)
    return result


# Kept for backwards compatibility with any external callers.
def fetch_accounts() -> list[dict[str, Any]]:
    """Flat list of accounts across all workspaces (no workspace tagging)."""
    return summarize_balance()["accounts"]
