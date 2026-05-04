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
    # removing IAM bindings; the URLs themselves never rot. Signed URLs
    # expire after 7 days, breaking the audit trail.
    #
    # Default is now "public" — REPS evidence is stored in a dedicated bucket
    # and the user wants permanent, login-free links so anyone (CPA, IRS) can
    # open them without needing a Google account. Grant `allUsers` viewer on
    # the bucket once via `gcloud storage buckets add-iam-policy-binding`.
    raw_style = (os.getenv("REPS_LINK_STYLE") or "").strip().lower()
    if raw_style in _VALID_LINK_STYLES:
        link_style = raw_style
    elif (os.getenv("REPS_PUBLIC_OBJECTS") or "").strip().lower() == "false":
        link_style = "auth"  # explicit opt-out
    else:
        link_style = "public"

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
    evidence_items: List["EvidenceItem"],
    location: Optional[str],
    material_participation_rentals: bool,
    people_involved: Iterable[str],
) -> Tuple[str, str]:
    """Append-only write. Returns `(spreadsheet_id, updated_range)`.

    Two-step strategy for the Evidence cell:
      1. `.append()` writes the row with the cell as plain newline-joined
         labels (still legible if step 2 fails).
      2. `batchUpdate.updateCells` rewrites just that one cell with rich
         text where each label segment carries a clickable `link.uri`. The
         row itself was created by `.append()` so the audit trail is still
         append-only — we never overwrite a previously-saved row.
    """

    cfg = get_config()
    sid = sheet_id_for_user(user, cfg)
    tab = cfg.sheet_tab
    _ensure_header(sid, tab)

    items = normalize_evidence_items(evidence_items)
    evidence_text = evidence_cell_text(items)

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
        evidence_text,
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

    # Step 2: enrich the just-appended evidence cell with clickable links.
    if items:
        row_idx = _row_index_from_updated_range(updated_range)
        if row_idx is not None:
            try:
                write_evidence_rich_text(sid, tab, row_idx, items)
            except Exception as exc:  # noqa: BLE001
                # Non-fatal — the labels are already in the cell as plain text.
                logger.warning(
                    "REPS append: rich-text update failed; cell will display "
                    "labels but won't be clickable. (%s)",
                    exc,
                )
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

    # Best-effort: pull the rich-text contents of the evidence column so the
    # in-app entries list can render each label as a clickable link. If the
    # rich-text fetch fails (transient API hiccup), we just fall back to the
    # plain-text label string already in `padded[7]`.
    evidence_by_row: dict[int, List[EvidenceItem]] = {}
    try:
        evidence_by_row = read_evidence_rich_text(sid, tab)
    except Exception as exc:  # noqa: BLE001
        logger.warning("REPS read: failed to read evidence rich-text (%s)", exc)

    out: list[dict] = []
    for row_idx, raw in enumerate(rows):
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
        items = evidence_by_row.get(row_idx, [])
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
                "evidence_items": [
                    {"url": it.url, "label": it.label or ""} for it in items
                ],
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


# --- Multi-asset evidence (flat per-property uploads) ------------------- #

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


def _property_folder_path(
    cfg: "RepsConfig",
    user: str,
    property_name: Optional[str],
) -> str:
    """`<base>/<user>/<property>/` — flat, one folder per property.

    No per-log subfolder anymore — files land directly under the property
    folder. Filenames carry the timestamp so collisions are impossible.
    """

    user_folder = USER_FOLDER_MAP[user]
    prop_slug = _slugify(property_name, _DEFAULT_SLUG_PROPERTY)
    return f"{cfg.base_prefix}/{user_folder}/{prop_slug}"


def _audit_filename(
    property_name: Optional[str],
    activity_category: Optional[str],
    log_dt: datetime,
    original_filename: str,
    index: int,
) -> str:
    """`<Property>_<Activity>_<YYYY-MM-DD_HHMMSS>_<rand>[_<idx>].<ext>`.

    HHMMSS + a 4-char random suffix make the name unique enough to keep
    every file in the property's flat folder without collisions, even
    when the user uploads two photos at the same minute.
    """

    ext = os.path.splitext(original_filename or "")[1].lower() or ".bin"
    prop = _slugify(property_name, _DEFAULT_SLUG_PROPERTY).title().replace("-", "")
    act = _slugify(activity_category, _DEFAULT_SLUG_ACTIVITY).title().replace("-", "")
    stamp = log_dt.astimezone(timezone.utc).strftime("%Y-%m-%d_%H%M%S")
    rand = uuid.uuid4().hex[:4]
    suffix = f"_{index}" if index > 0 else ""
    return f"{prop}_{act}_{stamp}_{rand}{suffix}{ext}"


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
    """Result of a multi-file upload.

    `folder_url` and `folder_path` are kept for API/frontend compatibility but
    are deliberately empty strings / None: we no longer maintain a per-log
    folder, and we no longer paste a folder link into the Sheet.
    """

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
    """Upload one or many evidence files into the property's flat folder.

    `items` is a list of `(original_filename, content_type, file_bytes)`.

    Returns one URL per file; the frontend then ships the URLs back to
    `/reps/log` paired with user-supplied labels so the Sheet can render
    each as a clickable named link.
    """

    if user not in USER_FOLDER_MAP:
        raise RepsValidationError(f"Unknown REPS user: {user!r}")
    if not items:
        raise RepsValidationError("upload_evidence_batch requires at least one file")

    log_dt = log_timestamp or datetime.now(timezone.utc)

    cfg = get_config()
    client = get_storage_client()
    bucket = client.bucket(cfg.bucket_name)

    folder_path = _property_folder_path(cfg, user, property_name)
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

    # Folder URL deliberately omitted — the Sheet now stores per-file labels
    # only. Frontend keeps the field for API compatibility.
    return UploadBatch(folder_url=None, folder_path=folder_path, files=uploaded)


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


# --- Evidence labels + rich-text helpers --- #

# Index of the Evidence column inside SHEET_COLUMNS — used when building the
# updateCells request that sets rich-text for the just-appended row. Kept as
# a function so reordering SHEET_COLUMNS does the right thing automatically.

def _evidence_column_index() -> int:
    return SHEET_COLUMNS.index("Evidence Link (GCS URL)")


@dataclass(frozen=True)
class EvidenceItem:
    """One uploaded evidence file paired with the user-provided display label.

    Stored in the Sheet as a clickable named link instead of the raw URL,
    so the auditor sees `Closing meeting` instead of a 240-char GCS URL.
    """

    url: str
    label: Optional[str] = None


def _safe_label(raw_label: Optional[str], fallback_url: str) -> str:
    """Single-line, trimmed display label for the evidence cell.

    Falls back to the URL's filename if the user didn't type anything.
    Newlines are collapsed because the cell uses `\n` as the separator
    between distinct evidence items.
    """

    base = (raw_label or "").strip()
    if not base:
        try:
            base = os.path.splitext(os.path.basename(fallback_url.split("?", 1)[0]))[0]
        except Exception:  # noqa: BLE001
            base = ""
    base = base or "evidence"
    base = re.sub(r"\s+", " ", base).strip()
    return base[:120]


def normalize_evidence_items(
    items: Iterable[Optional["EvidenceItem"]],
) -> List["EvidenceItem"]:
    """Drop empties + duplicates, sanitize labels."""

    out: List[EvidenceItem] = []
    seen: set[str] = set()
    for it in items or []:
        if not it:
            continue
        url = (it.url or "").strip()
        if not url or url in seen:
            continue
        seen.add(url)
        out.append(EvidenceItem(url=url, label=_safe_label(it.label, url)))
    return out


def evidence_cell_text(items: List["EvidenceItem"]) -> str:
    """Plain-text fallback the cell is initialized with on `.append()`.

    The labels are joined by `\n` so the visible text in the cell matches
    the rich-text we'll later write via `updateCells`. If the rich-text
    update fails for any reason (transient API error), the cell is still
    legible — just not clickable.
    """

    return "\n".join(it.label or "" for it in items if it)


def _resolve_sheet_id(spreadsheet_id: str, sheet_title: str) -> int:
    """Numeric `sheetId` (gridId) for the worksheet named `sheet_title`.

    `batchUpdate.updateCells` needs the numeric ID, not the title.
    """

    canon = _resolve_worksheet_title(spreadsheet_id, sheet_title)
    svc = get_sheets_client()
    meta = (
        svc.spreadsheets()
        .get(spreadsheetId=spreadsheet_id, fields="sheets(properties(title,sheetId))")
        .execute()
    )
    for s in meta.get("sheets") or []:
        prop = s.get("properties") or {}
        if prop.get("title") == canon:
            return int(prop.get("sheetId", 0))
    raise RepsValidationError(
        f"Unable to resolve sheetId for tab {canon!r} in spreadsheet …{spreadsheet_id[-12:]}."
    )


_A1_RANGE_ROW_RE = re.compile(r"!\s*[A-Z]+(\d+)\s*:\s*[A-Z]+\d+\s*$")


def _row_index_from_updated_range(updated_range: str) -> Optional[int]:
    """Parse the `updatedRange` returned by Sheets `.append()` to a 0-based row.

    Sheets returns ranges like `'Log'!A123:L123`. Returns `None` if we can't
    confidently parse it (in which case the rich-text update is skipped and
    we leave the plain-text labels in place — still legible to the auditor).
    """

    m = _A1_RANGE_ROW_RE.search(updated_range or "")
    if not m:
        return None
    try:
        return int(m.group(1)) - 1
    except (TypeError, ValueError):  # pragma: no cover
        return None


def write_evidence_rich_text(
    spreadsheet_id: str,
    sheet_title: str,
    row_index_zero_based: int,
    items: List["EvidenceItem"],
) -> None:
    """Replace the evidence cell with rich text where each label is a link.

    The cell value becomes the labels joined by `\n` and each label segment
    carries a `link.uri` so it renders as a clickable hyperlink in Sheets.
    No-ops if `items` is empty.
    """

    if not items:
        return

    sheet_id = _resolve_sheet_id(spreadsheet_id, sheet_title)
    col = _evidence_column_index()

    # Build the visible string + per-label link runs.
    text = evidence_cell_text(items)
    runs: List[dict] = []
    cursor = 0
    for it in items:
        label = it.label or ""
        if not label:
            cursor += 1  # the `\n` separator we'd still emit
            continue
        runs.append(
            {
                "startIndex": cursor,
                "format": {
                    "link": {"uri": it.url},
                    "underline": True,
                    "foregroundColor": {"red": 0.07, "green": 0.42, "blue": 0.78},
                },
            }
        )
        cursor += len(label) + 1  # +1 for the `\n` separator

    svc = get_sheets_client()
    svc.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={
            "requests": [
                {
                    "updateCells": {
                        "range": {
                            "sheetId": sheet_id,
                            "startRowIndex": row_index_zero_based,
                            "endRowIndex": row_index_zero_based + 1,
                            "startColumnIndex": col,
                            "endColumnIndex": col + 1,
                        },
                        "rows": [
                            {
                                "values": [
                                    {
                                        "userEnteredValue": {"stringValue": text},
                                        "textFormatRuns": runs,
                                    }
                                ]
                            }
                        ],
                        "fields": "userEnteredValue,textFormatRuns",
                    }
                }
            ]
        },
    ).execute()


def read_evidence_rich_text(
    spreadsheet_id: str,
    sheet_title: str,
) -> dict[int, List["EvidenceItem"]]:
    """Read the rich-text contents of the evidence column for every data row.

    Returns a map of `0-based-row-index -> [EvidenceItem]` so the caller can
    enrich `read_log_rows` output with clickable links for the in-app entries
    list. Pure read; no side effects.
    """

    canon = _resolve_worksheet_title(spreadsheet_id, sheet_title)
    col = _evidence_column_index()
    col_letter = _col_letter(col + 1)
    rng = f"{_quote_sheet_title_for_a1(canon)}!{col_letter}2:{col_letter}1048576"

    svc = get_sheets_client()
    res = (
        svc.spreadsheets()
        .get(
            spreadsheetId=spreadsheet_id,
            ranges=[rng],
            fields=(
                "sheets(data(rowData(values("
                "formattedValue,"
                "userEnteredValue/stringValue,"
                "textFormatRuns(startIndex,format(link/uri))"
                "))))"
            ),
        )
        .execute()
    )

    out: dict[int, List[EvidenceItem]] = {}
    sheets_data = (res.get("sheets") or [{}])[0].get("data") or [{}]
    row_data = sheets_data[0].get("rowData") or []
    for row_idx, row in enumerate(row_data):
        cells = row.get("values") or []
        if not cells:
            continue
        cell = cells[0]
        text: Optional[str] = (
            cell.get("userEnteredValue", {}).get("stringValue")
            or cell.get("formattedValue")
        )
        if not text:
            continue
        runs = cell.get("textFormatRuns") or []
        items: List[EvidenceItem] = []
        if runs:
            # Slice the visible string between consecutive run startIndexes.
            run_bounds = [(int(r.get("startIndex", 0)), r) for r in runs]
            run_bounds.sort(key=lambda p: p[0])
            for i, (start, run) in enumerate(run_bounds):
                end = run_bounds[i + 1][0] if i + 1 < len(run_bounds) else len(text)
                label = text[start:end].strip(" \n\r\t")
                if not label:
                    continue
                uri = (run.get("format") or {}).get("link", {}).get("uri")
                if uri:
                    items.append(EvidenceItem(url=uri, label=label))
        if items:
            out[row_idx] = items
    return out
