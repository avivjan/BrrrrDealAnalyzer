# REPS Tracker — Setup & Run Guide

This document explains how to wire the dual-user (Aviv / Yarden) REPS
(Real Estate Professional Status) tracker to Google Sheets + Google Cloud
Storage so the app can append log rows and upload evidence files.

The app is **graceful**: if the env vars below are missing, the rest of
BrrrrDealAnalyzer still runs normally and the REPS Tracker page shows a
yellow "not configured" banner. You can build & deploy first, then plug in
the secrets.

---

## 1. What you need from Google Cloud

You'll create one Google Cloud project that owns:

1. **One service account** with the right scopes.
2. **Two Google Sheets** (one per user) shared with the service account.
3. **One Google Cloud Storage bucket** (for evidence files) where the
   service account can read/write.

### 1a. Create the GCP project (if you don't have one)

```bash
gcloud projects create big-whales-reps-2026 --name="Big Whales REPS"
gcloud config set project big-whales-reps-2026
gcloud services enable sheets.googleapis.com storage.googleapis.com
```

### 1b. Create the service account + key

```bash
gcloud iam service-accounts create reps-writer \
  --display-name="REPS Tracker Writer"

# Grant the SA permission to write to GCS objects in your project
gcloud projects add-iam-policy-binding big-whales-reps-2026 \
  --member="serviceAccount:reps-writer@big-whales-reps-2026.iam.gserviceaccount.com" \
  --role="roles/storage.objectAdmin"

# Download a JSON key (keep this file SECRET — never commit it)
gcloud iam service-accounts keys create ~/secrets/reps-writer.json \
  --iam-account="reps-writer@big-whales-reps-2026.iam.gserviceaccount.com"
```

### 1c. Create the GCS bucket for evidence

```bash
# Pick a globally-unique name (replace below)
gcloud storage buckets create gs://bigwhales-reps-evidence-2026 \
  --location=us-central1 \
  --uniform-bucket-level-access
```

> If you want **public links** in the sheet (anyone with link can view the
> file), grant `roles/storage.objectViewer` to `allUsers` on the bucket and
> set `REPS_PUBLIC_OBJECTS=true` (see env vars). Otherwise, leave it
> private — the app will return time-limited (7-day) signed URLs.

### 1d. Create the two Google Sheets

In your browser, sign in as **the Big Whales google account that owns the
Drive folder** for these audit files.

1. Create a new Google Sheet titled **"REPS — Aviv 2026"**.
2. Create another titled **"REPS — Yarden 2026"**.
3. (Optional) Rename the first tab in each sheet to `Log` (matches the
   default `REPS_SHEET_TAB`). Otherwise, set `REPS_SHEET_TAB` to whatever
   you named your tab.
4. **Share both sheets** with your service-account email
   (`reps-writer@…iam.gserviceaccount.com`) as **Editor**.
5. Copy each sheet's **Spreadsheet ID** out of the URL:
   `https://docs.google.com/spreadsheets/d/<THIS_PART>/edit`

The app writes the header row (12 columns, in this order) on the first
append, so you don't need to set up columns manually:

| # | Column |
|---|--------|
| A | Timestamp (Created At) |
| B | User |
| C | Property Name |
| D | Activity Category |
| E | Description |
| F | Start Time |
| G | End Time |
| H | Total Hours (Decimal) |
| I | Evidence Link (GCS URL) |
| J | Location (GPS/Remote) |
| K | Material Participation in rentals? |
| L | People Involved |

---

## 2. Backend env vars

Add these to `BackEnd/.env` (or your deploy environment):

```env
# Where the JSON key file lives (absolute path on the server)
GOOGLE_APPLICATION_CREDENTIALS=/Users/avivjan/secrets/reps-writer.json

# Spreadsheet IDs (from step 1d)
REPS_SHEET_ID_AVIV=1AbCDe…AvivSheetId
REPS_SHEET_ID_YARDEN=1AbCDe…YardenSheetId

# (Optional) Tab name inside each spreadsheet — defaults to "Log"
REPS_SHEET_TAB=Log

# GCS bucket (from step 1c)
REPS_GCS_BUCKET=bigwhales-reps-evidence-2026

# (Optional) Folder prefix inside the bucket — defaults to "evidence/2026"
REPS_GCS_BASE_PREFIX=evidence/2026

# (Optional) "true" returns public URLs (requires bucket-level allUsers
# objectViewer); "false" (default) returns 7-day signed URLs.
REPS_PUBLIC_OBJECTS=false
```

> If you deploy on Cloud Run / GKE you can omit
> `GOOGLE_APPLICATION_CREDENTIALS` and the app will use Application
> Default Credentials from the runtime's metadata server. Make sure the
> runtime's service account is the same one (or another one) shared on
> both sheets and granted `storage.objectAdmin` on the bucket.

---

## 3. Install dependencies

The new Google client libs are already in `BackEnd/requirements.txt`:

```bash
cd BackEnd
pip install -r requirements.txt
```

(`python-multipart` is required for FastAPI's `UploadFile`; it is now in
the requirements file.)

---

## 4. Run it

```bash
# Backend (FastAPI)
cd BackEnd
uvicorn main:app --reload --port 8000

# Frontend (Vite)
cd frontend
npm install
npm run dev
```

Open <http://localhost:5173/>. From the landing page, click the new
**REPS Tracker** card (rose / amber gradient, clock icon).

If `/reps/config-status` reports `configured=false` you'll see a yellow
banner with the missing env vars; otherwise the dashboard, timer, modal,
and stats are live.

---

## 5. Quick smoke test (optional)

After setting env vars and running the backend:

```bash
# Should return {"configured": true, ...}
curl http://localhost:8000/reps/config-status

# Should append a row to Aviv's sheet
curl -X POST http://localhost:8000/reps/log \
  -H 'Content-Type: application/json' \
  -d '{
    "user": "Aviv2026",
    "property_name": "Honda",
    "activity_category": "Construction / Rehab Oversight",
    "description": "Met with Gilly at Honda to walk plumbing punch list",
    "start_time": "2026-05-03T09:00:00-04:00",
    "end_time": "2026-05-03T10:30:00-04:00",
    "material_participation_rentals": false,
    "people_involved": ["Gilly"]
  }'

# Should read your sheet rows + computed YTD stats
curl 'http://localhost:8000/reps/entries?user=Aviv2026'
```

---

## 6. New in v2 — Multi-asset evidence, real-time camera, GPS breadcrumbs, dynamic categories

The REPS Tracker now captures more audit-defensible context out of the box:

- **Device GPS breadcrumbs.** The browser auto-snaps `navigator.geolocation`
  on **Start / Stop / Pause / Resume**, on **"Pin GPS now"** during a
  session, on **"Save"** for any entry, and each time you snap a photo via
  the in-app camera. The full breadcrumb trail
  (`START 2026-05-03T18:01:00Z @ 25.7741,-80.1937 (±15m) — maps.google.com/?q=…`)
  is rendered into the **Location** column so the auditor can see you
  stayed at the property during the session. If the user denies location
  permission, the snapshot still goes into the trail with
  `[permission_denied]` so the audit log is honest, not silent.
- **Multi-asset evidence + real-time camera.** The modal accepts
  multiple files, supports `Camera` (uses `<input capture="environment">`
  to open the device's native camera) and `Attach`. Each log gets its own
  GCS sub-folder
  (`/<base_prefix>/<aviv|yarden>/<property-slug>/log_<utc_timestamp>_<rand>/`)
  and uploaded files are renamed
  `Property_Activity_YYYY-MM-DD_HHMM[_idx].ext` for grep-ability. The
  Sheet's **Evidence Link** column gets the folder URL on top followed by
  every individual file URL.
- **Real-time camera while clocked-in.** With the timer running you can
  hit **Take Photo / Video** straight from the timer card. The file is
  queued for that user's session and a `PHOTO` snapshot is added to the
  GPS breadcrumbs at the same moment.
- **Dynamic activity categories.** The dropdown is now backed by the
  `reps_activity_categories` table (seeded with sensible defaults on
  first boot). Click **Add new** in the modal to create one inline; the
  dropdown refreshes immediately and the new value is reused on the next
  entry. Endpoint: `GET/POST/DELETE /reps/activity-categories`.
- **File-count badge.** The modal shows a "N files attached" badge so
  you can verify your evidence is queued before saving. The Save button
  also shows an `Uploading N files...` state while the GCS batch upload
  runs.

No new env vars are required for any of this — the same
`GOOGLE_APPLICATION_CREDENTIALS`, `REPS_GCS_BUCKET`, `REPS_GCS_BASE_PREFIX`,
`REPS_PUBLIC_OBJECTS`, and the two `REPS_SHEET_ID_*` vars cover the new
behavior. **Don't forget to deploy over HTTPS** — `navigator.geolocation`
is gated to secure origins (`https://` or `localhost`).

---

## 7. How the audit-trail rules are enforced

| Spec rule | Where it's enforced |
|---|---|
| Append-only writes (no overwrites) | `reps_service.append_log_row` uses Sheets `.append()` exclusively. |
| Server-stamped `created_at` | `reps_service.now_utc_iso` is called inside `/reps/log` after the request hits the server. The user's "event date" is stored in `start_time` / `end_time`, never in column A. |
| User → sheet routing | `reps_service.sheet_id_for_user` maps `Aviv2026` → `REPS_SHEET_ID_AVIV` and `Yarden2026` → `REPS_SHEET_ID_YARDEN`. |
| GCS folder routing | `reps_service.upload_evidence` writes to `<base_prefix>/aviv/…` or `<base_prefix>/yarden/…`. |
| File-type whitelist | `.pdf, .jpg, .jpeg, .png, .mov, .mp4` — enforced both client-side (`<input accept>`) and server-side (`validate_evidence_file`). |
| Total Hours = decimal, 2 dp | `reps_service.calc_total_hours` computes `(end-start)/3600` using `Decimal.quantize`. |
| Description ≥ 20 chars | Pydantic validator on `RepsLogCreate.description` + live counter in the modal. |
| No edit button after append | The frontend entries list (`RepsEntriesList.vue`) is read-only — corrections must be a new entry. |
| Timer survives refresh / sleep | `repsStore.ts` persists `timer_state_aviv` / `timer_state_yarden` to `localStorage`; only the running segment's `startedAt` is wall-clocked, so refresh keeps the elapsed time accurate. |
| Aviv tab and Yarden tab independent | Two different localStorage keys + reactive timer record per user; switching tabs never touches the inactive user's state. |
| Property autocomplete = bought deals first, prospects after | `crud_reps.list_property_options` merges `BoughtBrrrDeal.address` + `BoughtFlipDeal.address` + `reps_properties` rows, dedupes case-insensitively, and tags each option `bought` / `prospect`. |
| New typed properties saved as Prospects | `RepsEntryModal.save` calls `store.ensureProspect(name)` before posting the log. |

---

## 8. Troubleshooting

- **400 / "Unable to parse range"** → usually `REPS_SHEET_TAB` does not
  match a tab at the bottom of the spreadsheet. New spreadsheets default
  to **Sheet1**; either rename that tab to `Log` **or** set
  `REPS_SHEET_TAB=Sheet1`. The backend now verifies the tab exists and
  returns `400` listing the tabs it found when the name is wrong.
- **404 / "Requested entity was not found"** → wrong `REPS_SHEET_ID_*`
  value, or the tab name doesn't exist (set `REPS_SHEET_TAB`).
- **`Permission denied` on bucket** → service account needs
  `roles/storage.objectAdmin` on the bucket (or just `objectCreator` +
  `objectViewer` if you want least privilege).
- **`make_public` fails** → the bucket has uniform-bucket-level access
  enabled (which is the default and recommended). Either grant
  `allUsers` `objectViewer` at the bucket level, or leave
  `REPS_PUBLIC_OBJECTS=false` to use signed URLs.
- **Timer drift** → the stopwatch only relies on the running segment's
  `startedAt` for the wall-clock portion; everything else is
  `accumulatedMs`. If you suspect drift, check that the tab using the
  timer is actually focused (browsers throttle background timers, but
  the math still adds up because we recompute from `Date.now()` rather
  than counting ticks).
