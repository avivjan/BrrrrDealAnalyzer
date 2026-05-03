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
    evidence_link: Optional[str] = Field(None, max_length=2000)
    location: Optional[str] = Field(None, max_length=200)
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
    location: Optional[str]
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
