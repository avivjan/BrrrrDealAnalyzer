# Property Inspection Checklist (plan)

Task name `PropertyInspection`. On approval this plan is copied to `tasks/todo/PropertyInspection.md`.
Branch: the session's required push branch `claude/relaxed-meitner-z0vzc9`, cut from the latest `main`.
CLAUDE.md asks for a branch named after the task. This session can only push to the branch above, so that name wins.
PR to `main` at the end.

## Context

Before every purchase we walk the house with an iPad and fill out a PDF checklist. Its job is to make sure we never buy without checking an expensive system. It does not estimate cost.
This replaces the PDF with a public, game-like inspection walkthrough:
- One item per card, sections as "levels", and "missions left" for the CRITICAL items.
- Per-item autosave that keeps working offline, camera photos, and a shareable summary.
- Logged-in users can link an inspection to a Bought Deal.

## What I found in the repo (and what it means)

| Area | Finding | Consequence |
|---|---|---|
| Backend auth | No global middleware. `main.py:86-94` adds `require_app_key` and `require_session()` to every router not in `PUBLIC_ROUTERS`. `member_loan` and `devices` are in that tuple and gate themselves. | A new **public router** joins `PUBLIC_ROUTERS`. All of its routes live under `/public/inspections/...`. The logged-in routes go in a second, normal router, protected by default. Global gates are untouched. |
| Gate modes | `AUTH_MODE` / `APP_KEY_MODE` default to `off`. **You chose: same gate as the rest of the site.** | Logged-in routes use the existing gates. Tests turn on `AUTH_MODE=enforce` to prove the 401s. |
| Rate limits | Custom, inside each handler, through `BL/auth/common/audit.py` `count_recent()` / `record()`, keyed per IP by `client_ip()`. Body limit middleware: 30 MB. | Reused. Per-route caps are added on top. |
| DB | SQLAlchemy 2 `Column` style, UUID PKs. `create_all` builds new tables at boot, so no migration step is needed. The schema golden is `tests/_regression_snapshots/schema.json`. | New tables only. Goldens are regenerated with `verify_regression.py snapshot`. |
| Bought Deals | Two tables, `bought_brrrr_deals` and `bought_flip_deals`, with no `name` field (address only). `GET /bought-deals` is authenticated. | **Conflicts with spec:** one `deal_id` FK cannot point at two tables. I use two nullable FKs, `linked_bought_brrrr_deal_id` and `linked_bought_flip_deal_id`, with `ON DELETE SET NULL` and a check that at most one is set. The picker reuses `GET /bought-deals`, which is already authenticated, and searches it client-side. |
| Storage | Drive uploads go through an HMAC-signed Apps Script web app (`integrations/google_drive_loan_agreements.gs`, `member_loan_google_drive.py`). **You chose Google Drive.** | See "Photo storage" below. |
| MCP | Tools are **generated from OpenAPI**: one per route, named after the route function (`mcp_server.py:_build_tools`). Each needs an entry in `DESCRIPTIONS`. Calls go in-process through the same gates. | The MCP task is: name the route functions well, add their descriptions and annotations, and exclude the binary photo routes. |
| Frontend router | A global `beforeEach` lets through only `meta.auth` routes. Login returns via `?next=`. | Add a `meta.public` check. **Conflict:** `App.vue` calls `fetchDeals()` on every page, and the axios 401 interceptor redirects to login. On a public page an anonymous visitor would be bounced to login, or would get the app-key gate. Fix: skip the global fetches on public routes, and don't redirect from public routes. |
| Nav | `nav.ts` `NAV_ITEMS`. `AppMobileNav` hardcodes `grid-cols-6`. Tests assert 6 items. | Add an "Inspections" tab, set mobile to 7 columns, and update both tests. |
| Design | Tokens, 4 looks × light/dark (`data-look`, `.dark`), GSAP core, `v-press` / `v-count-up`, `prefersReducedMotion()`, at most 500 ms per entrance, 44 px targets. Primitives include `UiProgressRing`, `UiSegmented`, `UiStepper`, `UiSaveStatus`, `UiDrawer`, `UiModalPanel`. | Built entirely on tokens and primitives. No look-specific CSS. New page spec at `design-system/brrrr-deal-analyzer/pages/inspection.md`. |
| CSP | `img-src` does not include the API origin. `connect-src` does. | Photos load with axios as blobs and display as `blob:` URLs. No CSP change. |
| Language | English, LTR. | English UI. |
| E2E | `e2e/flows`, `e2e/fixtures` and `e2e/golden` change only in a commit whose subject starts with `Golden update:`. | The new E2E flow and its golden go in their own `Golden update:` commit. |
| No camera compression or Web Share code exists yet | | Both are new, small, dependency-free utilities. |

## Photo storage: Google Drive via Apps Script (your choice)

- **Script:** a new Apps Script web app, `integrations/google_drive_inspection_photos.gs`, owned by bigwhalesllc@gmail.com.
  - It has its own secret, with the same HMAC and 5-minute timestamp scheme as the loan-agreements script.
  - Actions:
    - `save`: stores the JPEG in the Drive folder `property inspections/<YYYY-MM-DD> <address> (<first 8 chars of id>)`. The folder is created if needed. The folder name is built server-side from sanitized fields. Returns the file id.
    - `read`: returns the base64 of a file id, only if that file is inside `property inspections`.
    - `trash`: moves a file id to the trash, with the same folder check.
  - Bonus: every inspection's photos are also browsable in Drive.
- **Thumbnails in Postgres:** the client uploads two JPEGs in one request, the full image (≤1600 px, quality 0.8, ≤4 MB) and a 320 px thumbnail (≤150 KB). The full image goes to Drive. The thumbnail is stored as `bytea` on the photo row, so cards and the summary render instantly without calling Apps Script, which takes 1–3 s per call. Enlarging a photo fetches the full image through the backend, which reads it from Drive.
- **Backend client:** `BL/inspection/inspection_photo_google_drive.py`, the same shape as `member_loan_google_drive.py`. Env: `INSPECTION_PHOTOS_DRIVE_UPLOAD_URL` and `INSPECTION_PHOTOS_DRIVE_UPLOAD_SECRET`.
- **Failures:**
  - If Drive is unconfigured or fails, the upload returns `503 photo_storage_unavailable`, and the client keeps the photo queued and retries.
  - Tests replace the Drive client with a fake.
  - Deleting an inspection or a photo trashes the Drive file as best effort. A failed trash is logged and never blocks the delete.
- **No Pillow:** canvas re-encoding on the client already strips EXIF, including GPS. The server checks JPEG magic bytes and sizes.

## Visual concept and game flow

**Concept: "Walkthrough".** It should feel like a premium field app: a dark-first glass surface, the look's display face for headings, and tabular numerals. Status colours are the semantic tokens, always paired with an icon:
- OK: `positive` with ✓
- Repair: `warning` with a wrench
- Replace: `negative` with ↻

1. **Start screen** (`/inspections/new`): three big questions, one at a time: address (required), date (prefilled today), inspector name. A "Start walkthrough" button creates the inspection, saves it to "recent on this device", and goes to the map.
2. **Level map** (`/inspections/:id`, default view):
   - Two stacked level tiles, *Structure & Exterior* and *Utilities & Mechanicals*. Each has a `UiProgressRing`, an "n / m checked" count, and a row of item chips (tap one to jump to it).
   - A sticky header holds the address, an overall progress bar, the **Missions left** pill (count of CRITICAL items still unchecked; tapping it lists them), the save state ("Saving…", "Saved", "Offline – n changes queued"), and a "Link to deal" button.
3. **Item card** (one per screen, `/inspections/:id/items/:itemKey`):
   - **Questions are revealed one at a time.** Each reveal is a 180 ms slide and fade.
     1. Status, as a 4-way big segmented control with targets ≥56 px.
     2. Then each field in turn: choice chips, a year picker with an "Unknown" chip, or the windows counter (huge −/+ steppers).
     3. Follow-ups appear only when their condition matches: Septic → last pump date; Well → pump/filtration condition.
     4. Last, a "Photo / Note" row, with the item's prompt ("Photograph the data plate") as the photo button's label.
   - Answered questions collapse into a compact "answer line". Tapping one reopens that question.
   - Picking a status auto-advances to the next question. Every action is one or two taps.
   - **Next / previous:** swipe left or right (pointer events, ≥60 px threshold, ignored while scrolling vertically), or the big ◀ ▶ buttons in a bottom bar. The card slides in 220 ms.
4. **Rewards:**
   - A done item ticks its chip, with a ring-fill animation.
   - **Level complete:** a ≤500 ms burst of token-coloured particles around the ring, plus a "Level cleared" toast.
   - **Finish:** a full-screen celebration with stats (`v-count-up`): items checked, Repair count, Replace count, photos. It leads to the summary.
   - With reduced motion (the OS setting or the in-app switch), all of these become instant state changes.
5. **Finish gating:**
   - "Finish inspection" is disabled while missions are left, and shows "2 missions left: HVAC, Sewer".
   - "Finish anyway" opens a dialog that requires a typed reason (at least 10 characters). The reason is stored.
6. **Summary** (`/inspections/:id/summary`):
   - Start info.
   - Then Replace and Repair items, each with its fields, notes and photo thumbnails (tap to enlarge).
   - Then "Windows to replace: N".
   - Then OK items, collapsed.
   - A Share button uses `navigator.share` with a text summary and the inspection link. The fallback copies the text to the clipboard.
7. **Inspections tab** (`/inspections`):
   - "Recent on this device", from localStorage.
   - For logged-in users only, "All inspections" with a delete action.
   - A "New inspection" button.

## Checklist config (single source of truth)

- **Files:**
  - Canonical: `BackEnd/BL/inspection/inspection_checklist_config.json`.
  - Byte-identical copy: `frontend/src/inspection/inspectionChecklistConfig.json`. A backend test fails if the two differ. The README documents the one-line copy command.
- **Shape:** sections → items with:
  - `key`, `label`, `description`, `is_critical`, `photo_prompt?`
  - `fields[]`, each with `key`, `label`, `type`, `options?`, `show_when?: {field_key, equals}`
- **Field types:** `choice`, `year_or_unknown`, `text_or_unknown`, `counter` (`min`, `max`), `date`, `text`.
- Adding sections or items later (interior, lot, permits) is a config-only change. Both server-side validation and the UI are driven by it.

## Data model (new tables, built by `create_all`)

- `property_inspections`:
  - `id` (uuid4 PK, the unguessable URL id), `property_address`, `inspection_date`, `inspector_name`
  - `inspection_status` (`draft`/`completed`), `completed_at`, `completion_override_reason`
  - `linked_bought_brrrr_deal_id`, `linked_bought_flip_deal_id` (nullable FKs, `SET NULL`, check that at most one is set)
  - `created_at`, `updated_at`
- `property_inspection_items`:
  - `id`, `inspection_id` (FK, cascade), `item_key`
  - `item_status` (`not_checked`/`ok`/`repair`/`replace`), `item_notes`, `item_field_values` (JSON), `updated_at`
  - unique (`inspection_id`, `item_key`)
  - Rows are created lazily on the first PATCH. A missing row means "not checked".
- `property_inspection_photos`:
  - `id` (uuid4), `inspection_id` (FK, cascade), `item_key`
  - `drive_file_id`, `thumbnail_jpeg` (bytea), `full_image_byte_size`, `created_at`
- **Deleting a bought deal** sets the link to null. The inspection survives.

## API

**Public router** (in `PUBLIC_ROUTERS`, all under `/public/inspections`).
- Every write requires `X-Requested-With`. Every route validates everything server-side.
- JSON bodies are capped at 32 KB by a small per-route `Content-Length` dependency.

| Method + path | Route function (= MCP tool name) | Limit per IP |
|---|---|---|
| `POST /public/inspections` | `create_inspection` | 20/h |
| `GET /public/inspections/{inspection_id}` | `get_inspection` (start info, items, photo metadata, server-computed `summary`, `linked: bool`, **no deal data**) | 600/h |
| `PATCH /public/inspections/{inspection_id}` | `update_inspection_start_info` | 600/h |
| `PATCH /public/inspections/{inspection_id}/items/{item_key}` | `update_inspection_item`. `status`, `notes` and `field_values` are each optional. `field_values` is **merged** key by key, never replaced, so two people don't clobber each other. Values are checked against the config: unknown keys or options → 422; an unknown `item_key` → 404. | 1200/h |
| `POST /public/inspections/{inspection_id}/complete` | `complete_inspection`. Returns 409 `critical_items_unchecked` with the item keys, unless `override_reason` (10–500 chars) is given. | 60/h |
| `POST /public/inspections/{inspection_id}/items/{item_key}/photos` | `upload_inspection_photo` (multipart `full_image` + `thumbnail_image`). JPEG magic bytes only, ≤4 MB and ≤150 KB, at most 12 per item and 150 per inspection. | 300/h |
| `GET …/photos/{photo_id}/thumbnail`, `GET …/photos/{photo_id}/full` | binary, `nosniff`, `Cache-Control: private, max-age=86400` | 2000/h |
| `DELETE …/photos/{photo_id}` | `delete_inspection_photo` | 300/h |

- An unknown or invalid id returns 404, never 500. There is **no `GET /public/inspections`** (list).
- Text limits: address 3–300 characters, inspector name ≤120, notes ≤4000. Control characters are stripped.
- The date must be within ±2 years of today.

**Authenticated router** (normal gates):

| Method + path | Route function |
|---|---|
| `GET /inspections` | `list_inspections` (includes linked deal id, type and address) |
| `DELETE /inspections/{inspection_id}` | `delete_inspection` |
| `GET /inspections/{inspection_id}/deal-link` | `get_inspection_deal_link` (so a logged-in viewer can see which deal it is linked to) |
| `PUT /inspections/{inspection_id}/deal-link` `{bought_deal_id, deal_type}` | `link_inspection_to_deal` |
| `DELETE /inspections/{inspection_id}/deal-link` | `unlink_inspection_from_deal` |
| `GET /bought-deals/{deal_id}/inspections?deal_type=` | `list_bought_deal_inspections` (status, date, Repair/Replace count) |
| `POST /bought-deals/{deal_id}/inspections?deal_type=` | `create_inspection_for_bought_deal` (linked, address prefilled from the deal) |

The deal picker reuses the existing, authenticated `GET /bought-deals`.

## Frontend

- **Routes** (`meta.public: true`): `/inspections`, `/inspections/new`, `/inspections/:inspectionId`, `/inspections/:inspectionId/items/:itemKey`, `/inspections/:inspectionId/summary`.
- **Router and app changes:**
  - Guard: `if (to.meta.public) return true`.
  - `App.vue`: skip `fetchDeals` on public routes.
  - `api/index.ts`: no login redirect while the current route is public.
- **Code:**
  - `src/api/inspection.ts`
  - `src/stores/inspectionStore.ts`
  - Pure logic in `src/inspection/inspectionChecklistLogic.ts`: visible questions and follow-ups, item done-ness, level progress, critical items remaining, whether finishing is allowed, window counter clamping, and the share text.
  - `src/inspection/inspectionPhotoCompression.ts` (canvas → full and thumbnail JPEG)
  - `src/inspection/inspectionOfflineQueue.ts`: pending item patches go in localStorage `bw.inspection.pendingChanges.<id>`; pending photo blobs go in IndexedDB.
  - `src/inspection/inspectionRecentOnDevice.ts`: `bw.inspections.recentOnDevice`, with every read and write wrapped in try/catch.
- **Autosave:**
  - Each item is debounced at 600 ms, following the `BoughtDeals.vue` `useDebounceFn` pattern.
  - `UiSaveStatus` shows saving, saved or offline, plus "n queued".
  - On a network error the change stays queued and is retried on the `online` event and every 15 s.
  - Polling `GET` every 10 s while the tab is visible applies remote item changes, except for items with local edits still pending.
  - Creating an inspection needs a connection. Everything after that works offline.
- **Views:** `InspectionsHome.vue`, `InspectionStart.vue`, `InspectionWalkthrough.vue` (map and card), `InspectionSummary.vue`.
- **Components** in `components/inspection/`: `InspectionLevelMap`, `InspectionItemCard`, `InspectionStatusPicker`, `InspectionFieldQuestion`, `InspectionWindowReplacementCounter`, `InspectionPhotoStrip`, `InspectionPhotoLightbox`, `InspectionMissionsLeftPill`, `InspectionCelebration`, `InspectionFinishDialog`, `InspectionDealLinkDrawer`.
- **Linking:**
  - "Link to deal" when anonymous goes to `/login?next=/inspections/<id>`.
  - Logged in, it opens a drawer with a search box over `GET /bought-deals`, plus link and unlink.
- **Bought Deal modal** (`views/BoughtDeals.vue`): a new `BoughtDealLinkedInspectionsSection.vue` card after Pipeline Progress. It shows the linked inspections and a "New inspection" button, which creates a linked inspection and opens it.
- **Nav:** an `inspections` entry (`pi pi-check-square`), the mobile grid set to 7 columns, and the 6→7 counts in `nav.test.ts` and `AppSidebar.test.ts`.

## Todo (agent wall-clock)

- [x] **0** (10 min): Branch from the latest `main`. Copy this plan to `tasks/todo/PropertyInspection.md`.
- [x] **1** (30 min): Checklist config JSON (both copies) and the Python config loader and validator.
- [x] **2** (40 min): Models for the 3 tables, registered in `DAL/data_models/__init__.py`, plus `DAL/crud/inspection.py`.
- [x] **3** (75 min): `BL/inspection/` service: create, get with summary, merge-patch item, complete with gating and override, link and unlink, list. Pydantic schemas in `ReqRes/common/inspection_schemas.py`.
- [x] **4** (45 min): The public router and authenticated router, rate limits, body caps. Wire the public router into `PUBLIC_ROUTERS`.
- [x] **5** (60 min): Photos: the Apps Script, the HMAC Drive client, upload validation, thumbnail and full routes, delete with trash.
- [x] **6** (20 min): **MCP support:** `DESCRIPTIONS` for every new tool. `delete_inspection` and `unlink_inspection_from_deal` are destructive; GET tools are read-only. The binary photo routes are excluded from tool generation. MCP tests cover list, get with summary, create, update item, and link/unlink.
- [x] **7** (15 min): Update `test_auth_gate.py` so it exempts only `/public/inspections`. Regenerate the goldens with `verify_regression.py snapshot` and review the diff.
- [x] **8** (40 min): Frontend logic module, API client, store, offline queue, recent-on-device.
- [x] **9** (30 min): Router, nav and shell changes, and the fixes so public routes skip global fetches and the login redirect.
- [x] **10** (150 min): Walkthrough UI: start screen, level map, item card with progressive questions, status picker, counter, swipe, photos (compress, upload, thumbnails, lightbox, delete), missions-left pill, celebrations, finish dialog. Write the design page spec first.
- [x] **11** (45 min): Summary page and Share. The deal-link drawer. The Bought Deal linked-inspections section and "New inspection".
- [x] **12** (40 min): Vitest unit and component tests.
- [x] **13** (45 min): Playwright E2E flow and its golden, in a separate `Golden update:` commit.
- [x] **14** (40 min): **Security task** (from `.claude/security.md`): *"Please check through all the code you just wrote and make sure it follows security best practices. make sure there are no sensitive information in the frontend and there are no vulnerabilities that can be exploited throughout all the code in this repo"*. Specific checks:
  - No public route lists inspections or leaks deal fields. Add a test that walks every public response for `deal`, `brrrr` and `flip` keys.
  - The id is uuid4 only.
  - Rate limits and size caps work.
  - Only JPEG is accepted, and responses carry `nosniff`.
  - The Drive script checks the folder and HMAC, and its secret is never shipped to the frontend.
  - No `v-html` with user text.
  - The 401 redirect change doesn't weaken protected routes.
  - Then a repo-wide pass, and bandit, pip-audit and npm audit come back clean.
- [x] **15** (20 min): README: the feature, the new env vars, and the Apps Script setup steps. The Review section in the task file.
- [x] **16** (10 min): Push, open the PR ([#108](https://github.com/avivjan/BrrrrDealAnalyzer/pull/108)), CI green.
- [ ] **17** (you, ~10 min, guided): Deploy the Apps Script under bigwhalesllc. Set `INSPECTION_PHOTOS_DRIVE_UPLOAD_URL` and `INSPECTION_PHOTOS_DRIVE_UPLOAD_SECRET` on Render.

## Tests

**Unit (pytest, no DB):**
- The config validates.
- The backend and frontend configs are byte-identical.
- Field validation: options, year range or "unknown", counter bounds, follow-up keys.
- JPEG magic-byte check.
- HMAC signature matches the Apps Script's format.
- Summary computation.

**Integration (pytest, test Postgres, `AUTH_MODE=enforce` where relevant):**
- `test_public_inspection_endpoints_work_without_any_session_or_app_key` (with `APP_KEY_MODE=enforce` too)
- `test_no_public_endpoint_lists_inspections`: the OpenAPI has no GET on `/public/inspections`, and the route answers 405.
- `test_public_get_never_returns_deal_data_even_when_linked`
- `test_link_unlink_and_bought_deals_picker_return_401_without_session`
- `test_delete_inspection_requires_session`
- `test_completion_blocked_with_unchecked_critical_items` and `test_completion_override_requires_reason`
- `test_item_patch_merges_field_values_without_clobbering_other_fields`
- `test_photo_upload_rejects_non_jpeg_and_oversized_files` and `test_photo_count_limits`
- `test_public_inspection_rate_limit_returns_429`
- `test_unknown_or_malformed_inspection_id_returns_404`
- Deleting a deal sets the link to null; the deal's inspections list and its linked create work.
- Migration: a two-boot `import main` on a fresh DB (the CI smoke test), and the schema golden.

**MCP:** each new tool is listed with its annotations. Calling list, get, create, update item, and link/unlink works. The photo routes are absent.

**Frontend (Vitest):**
- Completion gating, with and without an override.
- Follow-up logic: septic shows the pump date; well shows the pump/filtration condition; switching back hides it.
- The window replacement counter clamps at its bounds, with a component test of the +/- buttons.
- Item done-ness and level progress.
- Offline queue: merging and replaying pending changes.
- Recent-on-device storage.
- Share text.
- Component and contract tests: `InspectionItemCard` reveals questions in order; `InspectionStatusPicker`; `InspectionFinishDialog`; nav count.

**E2E (Playwright):** start an inspection, check items through the map and by swiping, see the septic follow-up, step the window counter, see the finish blocked and then completed with an override, then the summary. A second test checks an anonymous visit to `/inspections/:id` lands on the inspection, not on login.

## Verification

1. Backend:
   ```bash
   cd BackEnd && pytest && python3 verify_regression.py verify
   ```
2. Frontend:
   ```bash
   cd frontend && npm test && npm run build && npm run e2e
   ```
3. Manual: run the app, open `/inspections/new` in a phone-sized viewport in a private window (anonymous), play through, toggle offline in devtools and confirm the queue syncs, and open the same inspection in two windows to see the polling merge.
4. MCP: `tests/mcp_helpers.call_json("get_inspection", inspection_id=...)` returns the summary.
5. CI on the PR: backend pytest and the migration smoke test, security, and frontend Vitest and build are all green.

## Review

| Check | Result |
|---|---|
| Backend `pytest` (test Postgres) | 1,225 passed, including `test_inspection_api.py` (26), `test_inspection_checklist_config.py` (14) and `test_mcp_inspection.py` (3) |
| Migration smoke test | Two `import main` boots on a fresh database: clean. The three tables come from `create_all`; no migration step needed |
| `verify_regression.py` | Only `openapi` and `schema` changed, both purely additive (12 new paths, 3 new tables); regenerated |
| Frontend `vitest` | 1,706 passed, including 32 new inspection tests |
| Frontend `npm run build` | Passes (`vue-tsc` and Vite) |
| Playwright | The new `inspection-walkthrough` flow passes on Chromium and Mobile Chrome; the full Chromium suite passes (121 passed, 4 skipped, as on `main`) |
| Security (CI's own checks) | bandit clean, pip-audit clean, `npm audit --omit=dev` 0 vulnerabilities |

**Deviations from the plan.**
1. **Rate limits are in memory**, per process (`inspection_request_guards.py`), not counted from `audit_log`. The autosave sends a request on almost every tap, and an audit row each time would flood that table. Render runs one process, and a restart only resets the counts.
2. **The card change is a CSS entrance**, not a Vue `<Transition mode="out-in">`. The out-in transition waited on animation frames before showing the next card. That is fragile, and it stalled completely under the E2E suite's frozen clock.
3. **Year questions use one stepper plus "Unknown"**, and show "≈ N years old" next to the year, so "age or install year" is a single answer.
4. **The MCP payload budget:** the MCP tools-list size budget in `test_mcp.py` went from 320 kB to 350 kB, recorded in that test's comment like the earlier raises.

**Security notes.**
1. **The per-IP limits see Netlify's address.** Production calls go through the Netlify `/api` proxy, so `client_ip()` (the last forwarded hop) is Netlify's egress address for everyone. That is true of every existing limit too (send-offer, ARV, member loan). The inspection limits are generous enough for two inspectors, but one abuser could use up the shared create limit (20 an hour) for a while. Fixing `client_ip()` for the proxy is a separate change.
2. **Inspection ids appear in Render's access logs**, as with any capability link. Only the owners can read those logs, and they can already read the database.
3. **Anyone with the link can edit the inspection and delete its photos**, as the spec intends. Only logged-in users can delete the inspection itself or change its deal link.
4. **An inspection started from a Bought Deal copies the deal's address** into the inspection. The public page then shows that address as the inspection's own field. No deal id, type or number is ever in a public response, and a test walks every public response to check.
5. **The Drive script** checks the HMAC and the timestamp, saves only `.jpg`, and reads or trashes only files under `property inspections`. Its secret exists only on Render and in the script's properties.
