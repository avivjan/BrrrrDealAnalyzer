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
- REPS_LINK_STYLE                 (Optional) How evidence URLs are written to
                                  the Sheet. One of:
                                    "auth"    Permanent
                                              `https://storage.cloud.google.com/...`
                                              link. Viewer must be signed in
                                              with a Google account that has
                                              read access (you / your CPA).
                                              **DEFAULT** — best for audit.
                                    "public"  Permanent
                                              `https://storage.googleapis.com/...`
                                              link. Bucket must be configured
                                              for public read access (grant
                                              `roles/storage.objectViewer` to
                                              `allUsers` at the bucket level
                                              when UBLA is on).
                                    "signed"  7-day expiring v4 signed URL.
                                              NOT recommended (links rot).
- REPS_PUBLIC_OBJECTS             (Deprecated; kept for backward compat)
                                  "true" implies REPS_LINK_STYLE="public".

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
# `Timestamp (Created At)` is the last column on purpose: the most useful
# columns for at-a-glance scanning (User → Property → Activity → Description
# → Start/End/Hours → Evidence → Location → Material Participation → People)
# stay on the left side of the viewport, and the server-stamped audit
# fingerprint sits in column L where it doesn't visually crowd the human-
# entered fields.
SHEET_COLUMNS: List[str] = [
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
    "Timestamp (Created At)",
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

_VALID_LINK_STYLES = {"auth", "public", "signed"}


@dataclass(frozen=True)
class RepsConfig:
    sheet_id_aviv: str
    sheet_id_yarden: str
    sheet_tab: str
    bucket_name: str
    base_prefix: str
    link_style: str  # "auth" | "public" | "signed"
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

    # Permanent-by-default link style. Auditors can still revoke access by
    # removing IAM bindings; the URLs themselves never rot. Signed URLs were
    # the previous default but they expire after 7 days, breaking the trail.
    raw_style = (os.getenv("REPS_LINK_STYLE") or "").strip().lower()
    if raw_style in _VALID_LINK_STYLES:
        link_style = raw_style
    elif (os.getenv("REPS_PUBLIC_OBJECTS") or "").strip().lower() == "true":
        link_style = "public"  # back-compat with the old toggle
    else:
        link_style = "auth"

    return RepsConfig(
        sheet_id_aviv=sheet_id_aviv,
        sheet_id_yarden=sheet_id_yarden,
        sheet_tab=os.getenv("REPS_SHEET_TAB", "Log"),
        bucket_name=bucket_name,
        base_prefix=os.getenv("REPS_GCS_BASE_PREFIX", "evidence/2026").strip("/"),
        link_style=link_style,
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

    # Order MUST match SHEET_COLUMNS exactly. created_at moved to the last
    # column so the auditor's eye lands on the human-entered fields first.
    row = [
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
        created_at_iso,
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
        # Indices below MUST match SHEET_COLUMNS:
        #   0 User · 1 Property · 2 Activity · 3 Description · 4 Start · 5 End
        #   6 TotalHours · 7 EvidenceLink · 8 Location · 9 MatlParticip
        #   10 People · 11 CreatedAt
        try:
            total_hours = float(padded[6]) if str(padded[6]).strip() else 0.0
        except (TypeError, ValueError):
            total_hours = 0.0
        people_str = padded[10] or ""
        people = [p.strip() for p in people_str.split(",") if p.strip()]
        out.append(
            {
                "user": padded[0] or None,
                "property_name": padded[1] or None,
                "activity_category": padded[2] or None,
                "description": padded[3] or None,
                "start_time": padded[4] or None,
                "end_time": padded[5] or None,
                "total_hours": total_hours,
                "evidence_link": padded[7] or None,
                "location": padded[8] or None,
                "material_participation_rentals": str(padded[9]).strip().upper() in {"TRUE", "1", "YES", "Y"},
                "people_involved": people,
                "created_at": padded[11] or None,
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
    return _make_url_for_blob(blob, cfg, object_name)


# --- Multi-asset evidence (batch upload to a per-log folder) ------------ #

# Slug used in object names when the user didn't pick a property/category.
_DEFAULT_SLUG_PROPERTY = "property"
_DEFAULT_SLUG_ACTIVITY = "log"


def _slugify(value: Optional[str], default: str) -> str:
    """Cheap, GCS-safe slug — lowercase, ASCII, words joined with `-`."""

    raw = (value or "").strip().lower()
    if not raw:
        return default
    cleaned = re.sub(r"[^a-z0-9]+", "-", raw).strip("-")
    return (cleaned or default)[:60]


def _log_folder_path(
    cfg: "RepsConfig",
    user: str,
    property_name: Optional[str],
    log_dt: datetime,
) -> str:
    """`<base>/<user>/<property>/log_YYYYMMDDTHHMMSS_<rand>/`."""

    user_folder = USER_FOLDER_MAP[user]
    prop_slug = _slugify(property_name, _DEFAULT_SLUG_PROPERTY)
    stamp = log_dt.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%S")
    rand = uuid.uuid4().hex[:6]
    return f"{cfg.base_prefix}/{user_folder}/{prop_slug}/log_{stamp}_{rand}"


def _audit_filename(
    property_name: Optional[str],
    activity_category: Optional[str],
    log_dt: datetime,
    original_filename: str,
    index: int,
) -> str:
    """`<Property>_<Activity>_<YYYY-MM-DD_HHMM>[_<idx>].<ext>` — easy to grep."""

    ext = os.path.splitext(original_filename or "")[1].lower() or ".bin"
    prop = _slugify(property_name, _DEFAULT_SLUG_PROPERTY).title().replace("-", "")
    act = _slugify(activity_category, _DEFAULT_SLUG_ACTIVITY).title().replace("-", "")
    stamp = log_dt.astimezone(timezone.utc).strftime("%Y-%m-%d_%H%M")
    suffix = f"_{index}" if index > 0 else ""
    return f"{prop}_{act}_{stamp}{suffix}{ext}"


def _make_url_for_blob(blob, cfg: "RepsConfig", object_name: str) -> str:
    """Return a stable URL for `object_name` according to `cfg.link_style`.

    - "auth"   permanent `https://storage.cloud.google.com/...` URL. The viewer
               must be signed in with a Google account that has read access to
               the object (you, a partner, or your CPA via IAM). DEFAULT.
    - "public" permanent `https://storage.googleapis.com/...` URL. Bucket must
               grant `roles/storage.objectViewer` to `allUsers` (UBLA-friendly).
               We attempt a legacy `make_public()` ACL flip as a best-effort for
               buckets without UBLA; on UBLA buckets it's a no-op and the URL
               only works if you set the bucket-level IAM yourself.
    - "signed" 7-day v4 signed URL. NOT permanent — links rot. Kept for ops
               who want zero IAM exposure.
    """

    style = cfg.link_style

    if style == "public":
        try:
            blob.make_public()
        except Exception as exc:  # pragma: no cover
            logger.info(
                "REPS upload: make_public no-op (bucket likely has UBLA); "
                "assuming bucket-level IAM grants allUsers:objectViewer. (%s)",
                exc,
            )
        return f"https://storage.googleapis.com/{cfg.bucket_name}/{object_name}"

    if style == "signed":
        try:
            return blob.generate_signed_url(
                version="v4",
                expiration=timedelta(days=7),
                method="GET",
            )
        except Exception as exc:  # pragma: no cover
            logger.warning("REPS upload: signed URL failed (%s); returning gs:// URI", exc)
            return f"gs://{cfg.bucket_name}/{object_name}"

    # Default: "auth" — permanent, requires viewer to be a signed-in Google
    # account with `storage.objects.get` on this object (or any role that
    # implies it: Storage Object Viewer, Project Viewer, etc.).
    return f"https://storage.cloud.google.com/{cfg.bucket_name}/{object_name}"


@dataclass(frozen=True)
class UploadedAsset:
    name: str
    url: str
    content_type: Optional[str]
    size_bytes: int


@dataclass(frozen=True)
class UploadBatch:
    folder_url: Optional[str]
    folder_path: str
    files: List[UploadedAsset]


def upload_evidence_batch(
    *,
    user: str,
    property_name: Optional[str],
    activity_category: Optional[str],
    log_timestamp: Optional[datetime],
    items: List[Tuple[str, Optional[str], bytes]],
) -> UploadBatch:
    """Upload one or many evidence files into a per-log GCS sub-folder.

    `items` is a list of `(original_filename, content_type, file_bytes)`.

    Returns the folder path / browseable folder URL plus per-file URLs that
    the frontend will hand back to `/reps/log` to be persisted in the Sheet.
    """

    if user not in USER_FOLDER_MAP:
        raise RepsValidationError(f"Unknown REPS user: {user!r}")
    if not items:
        raise RepsValidationError("upload_evidence_batch requires at least one file")

    log_dt = log_timestamp or datetime.now(timezone.utc)

    cfg = get_config()
    client = get_storage_client()
    bucket = client.bucket(cfg.bucket_name)

    folder_path = _log_folder_path(cfg, user, property_name, log_dt)
    uploaded: List[UploadedAsset] = []

    for idx, (orig_name, content_type, file_bytes) in enumerate(items):
        validate_evidence_file(orig_name, content_type)
        if not content_type:
            content_type = mimetypes.guess_type(orig_name)[0] or "application/octet-stream"

        new_name = _audit_filename(property_name, activity_category, log_dt, orig_name, idx)
        # Belt-and-suspenders: re-sanitize after the construction.
        new_name = sanitize_filename(new_name)
        object_name = f"{folder_path}/{new_name}"

        blob = bucket.blob(object_name)
        blob.upload_from_file(
            io.BytesIO(file_bytes),
            content_type=content_type,
            rewind=True,
        )
        url = _make_url_for_blob(blob, cfg, object_name)
        uploaded.append(
            UploadedAsset(
                name=new_name,
                url=url,
                content_type=content_type,
                size_bytes=len(file_bytes),
            )
        )

    folder_url: Optional[str] = None
    # Console folder browser — visible only to project members; convenient to
    # paste into the Sheet for auditors who have project access. Files
    # themselves are accessed via their (signed/public) URLs above.
    if cfg.bucket_name:
        folder_url = (
            f"https://console.cloud.google.com/storage/browser/"
            f"{cfg.bucket_name}/{folder_path}"
        )

    return UploadBatch(folder_url=folder_url, folder_path=folder_path, files=uploaded)


# --- Location snapshot rendering for the Sheet --- #

_KIND_LABELS: dict = {
    "manual_save": "MANUAL",
    "timer_start": "START",
    "timer_pause": "PAUSE",
    "timer_resume": "RESUME",
    "timer_stop": "STOP",
    "bookmark": "BOOKMARK",
    "evidence_capture": "PHOTO",
}


def _format_one_snapshot(snap: dict) -> str:
    """Render a single snapshot dict as a single audit-trail line.

    Produces e.g.  `START 2026-05-03T18:01:00Z @ 25.7741,-80.1937 (±15m) — https://maps.google.com/?q=25.7741,-80.1937`
    Falls back to "[no GPS]" + an optional note when coordinates are missing
    (user denied permission OR explicitly chose "Remote").
    """

    kind_raw = (snap.get("kind") or "").strip() or "bookmark"
    label = _KIND_LABELS.get(kind_raw, kind_raw.upper())

    captured_at = snap.get("captured_at") or ""
    if isinstance(captured_at, datetime):
        captured_at = captured_at.isoformat()

    lat = snap.get("lat")
    lng = snap.get("lng")
    accuracy = snap.get("accuracy_m")
    note = (snap.get("note") or "").strip()

    parts = [label, str(captured_at)]
    if lat is not None and lng is not None:
        coord = f"@ {float(lat):.5f},{float(lng):.5f}"
        if accuracy is not None:
            coord += f" (±{float(accuracy):.0f}m)"
        parts.append(coord)
        parts.append(f"— https://maps.google.com/?q={float(lat):.5f},{float(lng):.5f}")
    else:
        parts.append("[no GPS]")

    if note:
        parts.append(f"({note})")

    return " ".join(parts).strip()


def format_location_snapshots(
    snapshots: List[dict],
    fallback_note: Optional[str] = None,
) -> str:
    """Multi-line breadcrumb string the Sheet's Location column shows."""

    rendered: List[str] = []
    for snap in snapshots or []:
        try:
            rendered.append(_format_one_snapshot(snap))
        except Exception:  # noqa: BLE001
            # Never let a single bad reading kill the whole append.
            continue

    if rendered:
        return "\n".join(rendered)

    return (fallback_note or "").strip()


def join_evidence_links(
    folder_url: Optional[str],
    file_urls: List[str],
    legacy_single: Optional[str] = None,
) -> str:
    """One newline-joined string for the 'Evidence Link (GCS URL)' column.

    Folder URL on top (auditor's index page), then each file URL, then any
    legacy single-link backward-compat value.
    """

    out: List[str] = []
    if folder_url:
        out.append(folder_url.strip())
    for u in file_urls or []:
        u = (u or "").strip()
        if u and u not in out:
            out.append(u)
    if legacy_single and legacy_single.strip() and legacy_single.strip() not in out:
        out.append(legacy_single.strip())
    return "\n".join(out)
