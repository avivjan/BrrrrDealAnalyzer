"""Google Sheets + Google Cloud Storage integration for the REPS tracker.

Configuration (env vars):
- GOOGLE_APPLICATION_CREDENTIALS  Path to a service-account JSON key file with
                                  scopes: spreadsheets + cloud-platform.
                                  (If unset on Cloud Run, ADC is used.)
- REPS_SHEET_ID_AVIV              Google Sheet ID for user "Aviv2026".
- REPS_SHEET_ID_YARDEN            Google Sheet ID for user "Yarden2026".
- REPS_SHEET_TAB                  (Optional) Tab name to append to. Default "Log".
- REPS_GCS_BUCKET                 GCS bucket name for evidence uploads.
- REPS_GCS_BASE_PREFIX            (Optional) Top-level prefix in the bucket.
                                  Default "evidence/2026".
- REPS_PUBLIC_OBJECTS             (Optional) "true" | "false". When true the
                                  uploaded object is made public-read and the
                                  permanent public URL is returned. When false
                                  (default) a 7-day signed URL is returned.

Design notes:
- We use `.append()` exclusively (USER_ENTERED) so historical rows are never
  overwritten — append-only audit trail.
- The header row is created on first append if the sheet is empty.
- File uploads are routed to /evidence/2026/<aviv|yarden>/ inside the bucket.
- Module imports the Google libs lazily so the rest of the app boots even if
  the optional deps are missing.
"""

from __future__ import annotations

import io
import logging
import mimetypes
import os
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable, List, Optional, Tuple

logger = logging.getLogger(__name__)


# --- Sheet schema --------------------------------------------------------- #

# IMPORTANT: order matters — this is the column order persisted to Sheets.
SHEET_COLUMNS: List[str] = [
    "Timestamp (Created At)",
    "User",
    "Property Name",
    "Activity Category",
    "Description",
    "Start Time",
    "End Time",
    "Total Hours (Decimal)",
    "Evidence Link (GCS URL)",
    "Location (GPS/Remote)",
    "Material Participation in rentals?",
    "People Involved",
]

ALLOWED_EVIDENCE_EXTS = {".pdf", ".jpg", ".jpeg", ".png", ".mov", ".mp4"}
ALLOWED_EVIDENCE_MIME_PREFIXES = ("image/", "video/", "application/pdf")

USER_FOLDER_MAP = {
    "Aviv2026": "aviv",
    "Yarden2026": "yarden",
}


# --- Public errors -------------------------------------------------------- #

class RepsConfigError(RuntimeError):
    """Raised when required env vars / credentials are missing."""


class RepsValidationError(ValueError):
    """Raised on invalid file types / bad inputs."""


# --- Config helpers ------------------------------------------------------- #

@dataclass(frozen=True)
class RepsConfig:
    sheet_id_aviv: str
    sheet_id_yarden: str
    sheet_tab: str
    bucket_name: str
    base_prefix: str
    make_public: bool
    creds_path: Optional[str]


def get_config() -> RepsConfig:
    sheet_id_aviv = os.getenv("REPS_SHEET_ID_AVIV", "").strip()
    sheet_id_yarden = os.getenv("REPS_SHEET_ID_YARDEN", "").strip()
    bucket_name = os.getenv("REPS_GCS_BUCKET", "").strip()

    missing: list[str] = []
    if not sheet_id_aviv:
        missing.append("REPS_SHEET_ID_AVIV")
    if not sheet_id_yarden:
        missing.append("REPS_SHEET_ID_YARDEN")
    if not bucket_name:
        missing.append("REPS_GCS_BUCKET")
    if missing:
        raise RepsConfigError(
            "REPS feature is not fully configured. Missing env vars: "
            + ", ".join(missing)
            + ". See REPS_README.md for setup instructions."
        )

    return RepsConfig(
        sheet_id_aviv=sheet_id_aviv,
        sheet_id_yarden=sheet_id_yarden,
        sheet_tab=os.getenv("REPS_SHEET_TAB", "Log"),
        bucket_name=bucket_name,
        base_prefix=os.getenv("REPS_GCS_BASE_PREFIX", "evidence/2026").strip("/"),
        make_public=os.getenv("REPS_PUBLIC_OBJECTS", "false").lower() == "true",
        creds_path=os.getenv("GOOGLE_APPLICATION_CREDENTIALS") or None,
    )


def sheet_id_for_user(user: str, cfg: Optional[RepsConfig] = None) -> str:
    cfg = cfg or get_config()
    if user == "Aviv2026":
        return cfg.sheet_id_aviv
    if user == "Yarden2026":
        return cfg.sheet_id_yarden
    raise RepsValidationError(f"Unknown REPS user: {user!r}")


# --- Math helpers --------------------------------------------------------- #

def calc_total_hours(start: datetime, end: datetime) -> float:
    """Decimal hours rounded to 2 dp.

    Done server-side so the sheet column can be SUM()'d cleanly for the
    750-hour and 500-hour audit tests.
    """
    if end <= start:
        raise RepsValidationError("end_time must be strictly after start_time")
    delta_seconds = Decimal((end - start).total_seconds())
    hours = (delta_seconds / Decimal(3600)).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    return float(hours)


def now_utc_iso() -> Tuple[datetime, str]:
    """Single source of truth for the contemporaneous fingerprint."""
    now = datetime.now(timezone.utc)
    return now, now.isoformat()


# --- File-name sanitization ---------------------------------------------- #

_SAFE_FILENAME = re.compile(r"[^A-Za-z0-9._-]+")


def sanitize_filename(name: str) -> str:
    name = (name or "evidence").strip().replace(" ", "_")
    name = _SAFE_FILENAME.sub("_", name)
    return name[:120] or "evidence"


def validate_evidence_file(filename: str, content_type: Optional[str]) -> None:
    ext = os.path.splitext(filename or "")[1].lower()
    if ext not in ALLOWED_EVIDENCE_EXTS:
        raise RepsValidationError(
            f"File extension {ext!r} not allowed. Allowed: "
            + ", ".join(sorted(ALLOWED_EVIDENCE_EXTS))
        )
    # We enforce extension; mime type is best-effort.
    if content_type and not any(content_type.startswith(p) for p in ALLOWED_EVIDENCE_MIME_PREFIXES):
        # Don't hard-fail (browsers report .mov as application/octet-stream
        # sometimes); just log.
        logger.warning("REPS upload: unexpected mime %r for %s", content_type, filename)


# --- Google clients (lazy import) ---------------------------------------- #

_sheets_client = None
_storage_client = None


def _get_credentials(cfg: RepsConfig):
    """Resolve service-account credentials, preferring an explicit JSON file."""
    from google.oauth2 import service_account
    import google.auth

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/cloud-platform",
        "https://www.googleapis.com/auth/devstorage.read_write",
    ]
    if cfg.creds_path and os.path.exists(cfg.creds_path):
        return service_account.Credentials.from_service_account_file(
            cfg.creds_path, scopes=scopes
        )
    # Application Default Credentials (e.g. on Cloud Run / GKE).
    creds, _ = google.auth.default(scopes=scopes)
    return creds


def get_sheets_client():
    global _sheets_client
    if _sheets_client is not None:
        return _sheets_client
    try:
        from googleapiclient.discovery import build
    except ImportError as exc:  # pragma: no cover
        raise RepsConfigError(
            "Missing dependency `google-api-python-client`. Run "
            "`pip install -r BackEnd/requirements.txt`."
        ) from exc

    cfg = get_config()
    creds = _get_credentials(cfg)
    _sheets_client = build("sheets", "v4", credentials=creds, cache_discovery=False)
    return _sheets_client


def get_storage_client():
    global _storage_client
    if _storage_client is not None:
        return _storage_client
    try:
        from google.cloud import storage
    except ImportError as exc:  # pragma: no cover
        raise RepsConfigError(
            "Missing dependency `google-cloud-storage`. Run "
            "`pip install -r BackEnd/requirements.txt`."
        ) from exc

    cfg = get_config()
    creds = _get_credentials(cfg)
    _storage_client = storage.Client(credentials=creds, project=getattr(creds, "project_id", None))
    return _storage_client


# --- Sheets ops ---------------------------------------------------------- #

def _quote_sheet_title_for_a1(title: str) -> str:
    """Wrap a worksheet tab name for A1 ranges; escape embedded apostrophes per Sheets rules."""

    name = (title or "").strip()
    if not name:
        raise RepsValidationError("REPS sheet tab name is empty (set REPS_SHEET_TAB).")
    return "'" + name.replace("'", "''") + "'"


def _resolve_worksheet_title(spreadsheet_id: str, requested_tab: str) -> str:
    """Return the spreadsheet's canonical tab title for requested_tab.

    Google's error ``Unable to parse range: Sheet!…`` often indicates the tab named in
    REPS_SHEET_TAB does not exist (fresh spreadsheets default to "Sheet1").
    """

    svc = get_sheets_client()
    meta = (
        svc.spreadsheets()
        .get(spreadsheetId=spreadsheet_id, fields="sheets(properties(title))")
        .execute()
    )
    titles: List[str] = []
    for s in meta.get("sheets") or []:
        prop = s.get("properties") or {}
        t = prop.get("title")
        if isinstance(t, str) and t:
            titles.append(t)

    rq = (requested_tab or "").strip()
    if not rq:
        raise RepsValidationError(
            "REPS_SHEET_TAB is unset or empty. Set it to an existing worksheet name."
        )

    for t in titles:
        if t == rq:
            return t
    for t in titles:
        if t.lower() == rq.lower():
            return t

    raise RepsValidationError(
        f"Worksheet [{rq}] not found in spreadsheet …{spreadsheet_id[-12:]}. "
        f"Existing tab names: {titles!r}. "
        'Rename a tab to match or set REPS_SHEET_TAB (often "Sheet1" on new files).'
    )


def _a1_range(spreadsheet_id: str, configured_tab: str, cell_fragment: str) -> str:
    """Build a fully-qualified A1 range using a canonical, quoted worksheet title."""

    canon = _resolve_worksheet_title(spreadsheet_id, configured_tab)
    return f"{_quote_sheet_title_for_a1(canon)}!{cell_fragment}"


def _ensure_header(spreadsheet_id: str, tab: str) -> None:
    """Write the column header row if the sheet is empty. Idempotent."""
    svc = get_sheets_client()
    last_col = _col_letter(len(SHEET_COLUMNS))
    rng = _a1_range(spreadsheet_id, tab, f"A1:{last_col}1")
    res = (
        svc.spreadsheets()
        .values()
        .get(spreadsheetId=spreadsheet_id, range=rng)
        .execute()
    )
    values = res.get("values", [])
    if values and values[0]:
        return  # header already exists
    svc.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=rng,
        valueInputOption="USER_ENTERED",
        body={"values": [SHEET_COLUMNS]},
    ).execute()


def _col_letter(n: int) -> str:
    """1 -> A, 26 -> Z, 27 -> AA. Used to bound A1 ranges to the schema width."""
    out = ""
    while n > 0:
        n, r = divmod(n - 1, 26)
        out = chr(65 + r) + out
    return out


def append_log_row(
    user: str,
    created_at_iso: str,
    property_name: Optional[str],
    activity_category: Optional[str],
    description: str,
    start_iso: str,
    end_iso: str,
    total_hours: float,
    evidence_link: Optional[str],
    location: Optional[str],
    material_participation_rentals: bool,
    people_involved: Iterable[str],
) -> Tuple[str, str]:
    """Append-only write. Returns (spreadsheet_id, updated_range)."""
    cfg = get_config()
    sid = sheet_id_for_user(user, cfg)
    tab = cfg.sheet_tab
    _ensure_header(sid, tab)

    row = [
        created_at_iso,
        user,
        property_name or "",
        activity_category or "",
        description,
        start_iso,
        end_iso,
        total_hours,
        evidence_link or "",
        location or "",
        "TRUE" if material_participation_rentals else "FALSE",
        ", ".join(sorted({p.strip() for p in people_involved if p and p.strip()})),
    ]
    svc = get_sheets_client()
    last_col = _col_letter(len(SHEET_COLUMNS))
    rng = _a1_range(sid, tab, f"A:{last_col}")
    res = (
        svc.spreadsheets()
        .values()
        .append(
            spreadsheetId=sid,
            range=rng,
            valueInputOption="USER_ENTERED",
            insertDataOption="INSERT_ROWS",
            body={"values": [row]},
        )
        .execute()
    )
    updated_range = res.get("updates", {}).get("updatedRange", "")
    return sid, updated_range


def read_log_rows(user: str) -> list[dict]:
    """Read all data rows (excluding header) and project them to dicts.

    Numeric columns are best-effort: malformed values are skipped silently
    so a typo in the sheet doesn't 500 the dashboard.
    """
    cfg = get_config()
    sid = sheet_id_for_user(user, cfg)
    tab = cfg.sheet_tab
    _ensure_header(sid, tab)

    svc = get_sheets_client()
    last_col = _col_letter(len(SHEET_COLUMNS))
    # Fully-specified rectangular range avoids ambiguous parsers (e.g. "A2:L"
    # without row on the RHS).
    data_rng = _a1_range(sid, tab, f"A2:{last_col}1048576")
    res = (
        svc.spreadsheets()
        .values()
        .get(
            spreadsheetId=sid,
            range=data_rng,
        )
        .execute()
    )
    rows = res.get("values", []) or []

    out: list[dict] = []
    for raw in rows:
        # pad short rows so missing trailing cells become "".
        padded = list(raw) + [""] * (len(SHEET_COLUMNS) - len(raw))
        try:
            total_hours = float(padded[7]) if str(padded[7]).strip() else 0.0
        except (TypeError, ValueError):
            total_hours = 0.0
        people_str = padded[11] or ""
        people = [p.strip() for p in people_str.split(",") if p.strip()]
        out.append(
            {
                "created_at": padded[0] or None,
                "user": padded[1] or None,
                "property_name": padded[2] or None,
                "activity_category": padded[3] or None,
                "description": padded[4] or None,
                "start_time": padded[5] or None,
                "end_time": padded[6] or None,
                "total_hours": total_hours,
                "evidence_link": padded[8] or None,
                "location": padded[9] or None,
                "material_participation_rentals": str(padded[10]).strip().upper() in {"TRUE", "1", "YES", "Y"},
                "people_involved": people,
            }
        )
    return out


# --- GCS ops ------------------------------------------------------------- #

def upload_evidence(
    user: str,
    file_bytes: bytes,
    original_filename: str,
    content_type: Optional[str],
) -> str:
    """Upload to /evidence/2026/<user-folder>/<uuid>_<sanitized-name> and
    return a permanent URL the frontend can store in the sheet."""

    if user not in USER_FOLDER_MAP:
        raise RepsValidationError(f"Unknown REPS user: {user!r}")

    validate_evidence_file(original_filename, content_type)

    cfg = get_config()
    client = get_storage_client()
    bucket = client.bucket(cfg.bucket_name)

    safe_name = sanitize_filename(original_filename)
    object_name = (
        f"{cfg.base_prefix}/{USER_FOLDER_MAP[user]}/"
        f"{datetime.utcnow():%Y%m%dT%H%M%S}_{uuid.uuid4().hex[:8]}_{safe_name}"
    )
    blob = bucket.blob(object_name)

    if not content_type:
        content_type = mimetypes.guess_type(safe_name)[0] or "application/octet-stream"

    blob.upload_from_file(io.BytesIO(file_bytes), content_type=content_type, rewind=True)

    if cfg.make_public:
        try:
            blob.make_public()
            return blob.public_url
        except Exception as exc:  # pragma: no cover
            logger.warning("REPS upload: make_public failed (%s); falling back to signed URL", exc)

    # Signed URL good for 7 days — long enough for "permanent link" use cases
    # without exposing the bucket; the sheet still has the underlying object
    # path embedded in the URL for re-signing later.
    try:
        return blob.generate_signed_url(
            version="v4",
            expiration=timedelta(days=7),
            method="GET",
        )
    except Exception as exc:  # pragma: no cover
        logger.warning("REPS upload: signed URL failed (%s); returning gs:// URI", exc)
        return f"gs://{cfg.bucket_name}/{object_name}"
