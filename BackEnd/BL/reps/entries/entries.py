"""Read the user's full sheet history and return entries + computed stats.

Raises `reps_service.RepsConfigError` / `RepsValidationError` on failure; any
other exception propagates too -- the router maps all three to HTTP responses.
"""

from ReqRes.common.reps_schemas import RepsEntriesEnvelope, RepsEntryRow
from BL.reps.common import reps_service
from BL.reps.common.stats import compute_stats


def get_entries(user: str) -> RepsEntriesEnvelope:
    rows = reps_service.read_log_rows(user)
    return RepsEntriesEnvelope(
        user=user,  # type: ignore[arg-type]
        entries=[RepsEntryRow(**r) for r in rows],
        stats=compute_stats(user, rows),
    )
