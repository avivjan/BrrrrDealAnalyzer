"""Append a new REPS entry to the user's Google Sheet (append-only).

Evidence: each `evidence_items` entry becomes a clickable named link in
the Sheet's Evidence column (rich text). The user types the label in
the modal so the auditor sees `Closing meeting` instead of a 240-char
GCS URL.

Location: `location_snapshots` get rendered as breadcrumbs (START/STOP/
PAUSE/RESUME/BOOKMARK/MANUAL/PHOTO) so an auditor can verify the user
stayed at the property during the session.

Raises `reps_service.RepsConfigError` / `RepsValidationError` on failure; any
other exception propagates too -- the router maps all three to HTTP responses.
"""

import logging

from sqlalchemy.orm import Session

from ReqRes.common.reps_schemas import RepsLogCreate, RepsLogRes, EvidenceItem, RepsActivityCategoryCreate
from BL.reps.common import reps_service
from DAL.crud.reps import add_activity_category

logger = logging.getLogger(__name__)


def create_log(db: Session, payload: RepsLogCreate) -> RepsLogRes:
    # Server-generated contemporaneous fingerprint, regardless of any
    # user-selected event date.
    _, created_at_iso = reps_service.now_utc_iso()
    total_hours = reps_service.calc_total_hours(
        payload.start_time, payload.end_time
    )

    rendered_location = reps_service.format_location_snapshots(
        [s.model_dump() for s in payload.location_snapshots],
        fallback_note=payload.location,
    )

    # Prefer the v3 `evidence_items` schema; fall back to the legacy
    # `evidence_links`/`evidence_link` fields with no custom labels.
    items: list[reps_service.EvidenceItem]
    if payload.evidence_items:
        items = [
            reps_service.EvidenceItem(url=it.url, label=it.label)
            for it in payload.evidence_items
        ]
    else:
        legacy_urls = list(payload.evidence_links or [])
        if payload.evidence_link:
            legacy_urls.append(payload.evidence_link)
        items = [reps_service.EvidenceItem(url=u, label=None) for u in legacy_urls]

    items = reps_service.normalize_evidence_items(items)

    sid, updated_range = reps_service.append_log_row(
        user=payload.user,
        created_at_iso=created_at_iso,
        property_name=payload.property_name,
        activity_category=payload.activity_category,
        description=payload.description,
        start_iso=payload.start_time.isoformat(),
        end_iso=payload.end_time.isoformat(),
        total_hours=total_hours,
        evidence_items=items,
        location=rendered_location or None,
        material_participation_rentals=payload.material_participation_rentals,
        people_involved=payload.people_involved,
    )

    # If the user typed a brand-new activity category in the modal, persist
    # it so it shows up next time. Idempotent.
    if payload.activity_category and payload.activity_category.strip():
        try:
            add_activity_category(
                db,
                RepsActivityCategoryCreate(name=payload.activity_category.strip()),
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to persist new activity category: %s", exc)

    rendered_evidence = reps_service.evidence_cell_text(items)
    res_items = [EvidenceItem(url=it.url, label=it.label) for it in items]

    return RepsLogRes(
        created_at=created_at_iso,
        user=payload.user,
        property_name=payload.property_name,
        activity_category=payload.activity_category,
        description=payload.description,
        start_time=payload.start_time.isoformat(),
        end_time=payload.end_time.isoformat(),
        total_hours=total_hours,
        evidence_items=res_items,
        evidence_link=rendered_evidence or None,
        evidence_links=[it.url for it in items],
        evidence_folder=None,
        location=rendered_location or None,
        location_snapshots=payload.location_snapshots,
        material_participation_rentals=payload.material_participation_rentals,
        people_involved=payload.people_involved,
        spreadsheet_id=sid,
        appended_range=updated_range,
    )
