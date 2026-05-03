"""Pydantic request/response schemas for the REPS (Real Estate Professional
Status) tracking feature. Two users — Aviv2026 / Yarden2026 — log activity
into per-user Google Sheets and upload evidence to GCS.

Field names mirror the Google Sheet column order so the backend can
serialize a row with a single ordered list. See `reps_service.SHEET_COLUMNS`.
"""

from datetime import datetime
from typing import List, Literal, Optional
from pydantic import BaseModel, Field, field_validator

# Hard-coded user IDs — the only two valid values for the dual-tab tracker.
RepsUser = Literal["Aviv2026", "Yarden2026"]

# Minimum description length: enforced both client- and server-side to
# discourage vague entries like "Worked on house". The longer wording from
# our manual logs (e.g. "Met with Gilly at Honda to review plumbing issues")
# survives an audit much better.
MIN_DESCRIPTION_LEN = 20

# All allowed event types for a location snapshot. The auditor reads these as
# breadcrumbs in the Sheet's Location column, so order matters in the UI but
# the backend treats them as opaque labels here.
LocationSnapshotKind = Literal[
    "manual_save",
    "timer_start",
    "timer_pause",
    "timer_resume",
    "timer_stop",
    "bookmark",
    "evidence_capture",
]


class LocationSnapshot(BaseModel):
    """One device-GPS reading captured by the browser at a discrete event.

    `lat` / `lng` may be omitted when the user denied permission OR explicitly
    chose "Mark as Remote" — in which case `note` carries the override
    ("Remote", "permission_denied", etc.).
    """

    kind: LocationSnapshotKind
    captured_at: datetime
    lat: Optional[float] = Field(None, ge=-90, le=90)
    lng: Optional[float] = Field(None, ge=-180, le=180)
    accuracy_m: Optional[float] = Field(None, ge=0, le=1_000_000)
    note: Optional[str] = Field(None, max_length=200)


class RepsLogCreate(BaseModel):
    """Payload accepted by `POST /reps/log`.

    The backend overrides `created_at` server-side to a contemporaneous
    ISO timestamp; clients may pass it but it will be ignored.
    """

    user: RepsUser
    property_name: Optional[str] = Field(None, max_length=200)
    activity_category: Optional[str] = Field(None, max_length=100)
    description: str = Field(..., min_length=MIN_DESCRIPTION_LEN, max_length=5000)
    start_time: datetime
    end_time: datetime
    # NEW: array of evidence URLs (the modal uploads files via /reps/upload-batch
    # before calling /reps/log, then sends back the resulting URLs). Backed by
    # the GCS folder that holds them; the folder URL — when present — comes
    # first so the auditor sees the index page on top.
    evidence_links: List[str] = Field(default_factory=list)
    evidence_folder: Optional[str] = Field(None, max_length=2000)
    # Legacy single-link field — accepted for backward compatibility, merged
    # into `evidence_links` server-side.
    evidence_link: Optional[str] = Field(None, max_length=2000)
    # NEW: device-GPS breadcrumbs across the session. The backend formats
    # these into a single human-readable string for the Sheet's Location col.
    location_snapshots: List[LocationSnapshot] = Field(default_factory=list)
    # Legacy free-text field — accepted as a single fallback "note" if no
    # snapshots are sent.
    location: Optional[str] = Field(None, max_length=2000)
    material_participation_rentals: bool = False
    people_involved: List[str] = Field(default_factory=list)

    @field_validator("end_time")
    @classmethod
    def _end_after_start(cls, v: datetime, info):
        start = info.data.get("start_time")
        if start and v <= start:
            raise ValueError("end_time must be strictly after start_time")
        return v

    @field_validator("description")
    @classmethod
    def _description_substantive(cls, v: str) -> str:
        v = v.strip()
        if len(v) < MIN_DESCRIPTION_LEN:
            raise ValueError(
                f"Description must be at least {MIN_DESCRIPTION_LEN} characters "
                f"(got {len(v)})."
            )
        return v


class RepsLogRes(BaseModel):
    """Echoed back to the caller after a successful append."""

    created_at: str
    user: RepsUser
    property_name: Optional[str]
    activity_category: Optional[str]
    description: str
    start_time: str
    end_time: str
    total_hours: float
    evidence_link: Optional[str]
    evidence_links: List[str] = Field(default_factory=list)
    evidence_folder: Optional[str] = None
    location: Optional[str]
    location_snapshots: List[LocationSnapshot] = Field(default_factory=list)
    material_participation_rentals: bool
    people_involved: List[str]
    spreadsheet_id: str
    appended_range: str


class RepsEntryRow(BaseModel):
    """One historical row read back from the user's sheet for stats / list view."""

    created_at: Optional[str] = None
    user: Optional[str] = None
    property_name: Optional[str] = None
    activity_category: Optional[str] = None
    description: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    total_hours: float = 0.0
    evidence_link: Optional[str] = None
    location: Optional[str] = None
    material_participation_rentals: bool = False
    people_involved: List[str] = Field(default_factory=list)


class RepsStats(BaseModel):
    """Year-to-date totals derived from the user's sheet rows."""

    user: RepsUser
    total_hours: float
    material_hours: float
    non_material_hours: float
    entry_count: int
    days_elapsed: int
    days_in_year: int
    year_progress_pct: float
    reps_750_pct: float
    material_500_pct: float
    avg_daily_hours_total: float
    avg_daily_hours_material: float


class RepsEntriesEnvelope(BaseModel):
    user: RepsUser
    entries: List[RepsEntryRow]
    stats: RepsStats


class RepsPersonCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    role: Optional[str] = Field(None, max_length=100)
    notes: Optional[str] = Field(None, max_length=2000)


class RepsPersonUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    role: Optional[str] = Field(None, max_length=100)
    notes: Optional[str] = Field(None, max_length=2000)


class RepsPersonRes(BaseModel):
    id: str
    name: str
    role: Optional[str]
    notes: Optional[str]
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class RepsPropertyOption(BaseModel):
    """One option in the Property Name autocomplete."""

    name: str
    source: Literal["bought", "prospect"]


class RepsPropertyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)


# --- Activity categories --- #

class RepsActivityCategoryRes(BaseModel):
    id: str
    name: str
    sort_order: int = 0
    is_default: bool = False


class RepsActivityCategoryCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)


# --- Multi-file upload response --- #

class RepsUploadedFile(BaseModel):
    name: str
    url: str
    content_type: Optional[str] = None
    size_bytes: int = 0


class RepsUploadBatchRes(BaseModel):
    folder_url: Optional[str] = None
    folder_path: str
    files: List[RepsUploadedFile] = Field(default_factory=list)
