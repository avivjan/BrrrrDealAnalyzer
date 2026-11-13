"""POST /webhooks/mercury/{receiving_path_token} -- Mercury calls this when something moves in an LLC with instant
updates on (tasks/todo/ConstructionAccountPerRehab.md, Step F).

Public (Mercury has no session), so it protects itself: the address carries a random token only Mercury knows, the
`Mercury-Signature` header must match (HMAC-SHA256, constant-time) and be under 5 minutes old, the body is capped, and
each address is rate limited. A valid event only means "read this LLC now": its contents are never trusted, stored or
logged. Never an MCP tool.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import deque
from datetime import datetime, timezone
from typing import Deque, Dict

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from BL.liquidity.common.mercury_webhooks import SIGNATURE_HEADER
from BL.liquidity.constructionAccount import mercury_instant_updates as instant_updates_bl
from BL.liquidity.dealCashRows.liquidity_deals import today_for_liquidity
from db import SessionLocal, get_db

logger = logging.getLogger(__name__)
router = APIRouter()

MAXIMUM_EVENT_BODY_BYTES = 64 * 1024
EVENTS_PER_MINUTE_PER_ADDRESS = 120
LONGEST_DEFERRED_READ_WAIT_SECONDS = 300
_event_times_by_address: Dict[str, Deque[float]] = {}
_event_times_lock = threading.Lock()
_workspaces_with_a_deferred_read: set[str] = set()
_deferred_reads_lock = threading.Lock()


def reset_mercury_webhook_rate_limits() -> None:
    """Tests start every case with empty windows."""
    with _event_times_lock:
        _event_times_by_address.clear()


def _within_the_rate_limit(receiving_path_token: str) -> bool:
    now = time.monotonic()
    with _event_times_lock:
        if len(_event_times_by_address) > 1000:
            _event_times_by_address.clear()
        times = _event_times_by_address.setdefault(receiving_path_token, deque())
        while times and now - times[0] > 60:
            times.popleft()
        if len(times) >= EVENTS_PER_MINUTE_PER_ADDRESS:
            return False
        times.append(now)
        return True


def read_the_workspace_once_the_floor_ends(mercury_workspace_label: str, read_not_before: datetime) -> None:
    """The one read an event inside the floor (or a back-off) waits for. More events meanwhile add no second read."""
    with _deferred_reads_lock:
        if mercury_workspace_label in _workspaces_with_a_deferred_read:
            return
        _workspaces_with_a_deferred_read.add(mercury_workspace_label)
    try:
        wait_seconds = (read_not_before - datetime.now(timezone.utc)).total_seconds()
        time.sleep(min(max(0.0, wait_seconds), LONGEST_DEFERRED_READ_WAIT_SECONDS))
        with SessionLocal() as db:
            instant_updates_bl.apply_an_instant_update(db, mercury_workspace_label, today_for_liquidity(db, None))
            db.commit()
    except Exception as error:   # a background read must never take the process down
        logger.warning("Mercury deferred read failed: %s", type(error).__name__)
    finally:
        with _deferred_reads_lock:
            _workspaces_with_a_deferred_read.discard(mercury_workspace_label)


@router.post("/webhooks/mercury/{receiving_path_token}", include_in_schema=False)
async def receive_mercury_webhook_event(receiving_path_token: str, request: Request, background_tasks: BackgroundTasks,
                                        db: Session = Depends(get_db)):
    if not (16 <= len(receiving_path_token) <= 80) or not _within_the_rate_limit(receiving_path_token):
        raise HTTPException(status_code=429 if len(receiving_path_token) >= 16 else 404, detail="Not accepted")
    raw_body = await request.body()
    if len(raw_body) > MAXIMUM_EVENT_BODY_BYTES:
        raise HTTPException(status_code=413, detail="Too large")
    try:
        outcome = instant_updates_bl.receive_mercury_event(db, receiving_path_token, raw_body, request.headers.get(SIGNATURE_HEADER),
                                                           today_for_liquidity(db, None))
    except instant_updates_bl.UnknownWebhookAddressError:
        db.rollback()
        raise HTTPException(status_code=404, detail="Not found")
    except instant_updates_bl.InvalidWebhookEventError:
        db.commit()   # the drawer shows the failed check
        raise HTTPException(status_code=401, detail="Not accepted")
    except Exception:
        db.rollback()
        raise
    db.commit()
    if not outcome.was_read_now and outcome.deferred_read_not_before is not None:
        background_tasks.add_task(read_the_workspace_once_the_floor_ends, outcome.mercury_workspace_label, outcome.deferred_read_not_before)
    return {"received": True}
