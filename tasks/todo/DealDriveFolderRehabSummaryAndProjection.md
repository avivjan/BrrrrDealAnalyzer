# DealDriveFolderRehabSummaryAndProjection: each Bought deal's own Drive folder, the rehab summary in its "Rehab" subfolder, and "HTML to Drive"

Branch `DealDriveFolderRehabSummaryAndProjection`, from `LoanAgreementsInDocsFolder` (which holds the change to `docs/loan agreements`, commit `dfe297b`), so one PR carries all three asks. No implementation code until you approve this plan.

## Context
- **Already done:** signed loan agreements now save to `docs/loan agreements`. You redeployed that script and tested it.
- **Rehab summary:** it was going to one shared `rehab summaries/` tree through a script you never deployed. Instead, each Bought deal gets its own Drive folder, the deal's existing **Google Drive Link** field, which you own. The summary goes into a `Rehab` subfolder there.
- **Required link:** when a deal moves to Bought, the link must be filled with a valid Google Drive folder.
- **New "HTML to Drive"** on a Bought deal: it generates the interactive HTML deal report (the same one as today's HTML report download) and saves it in the deal's folder, under `<date>/deal projection.html`.

## Design
- **One Apps Script for deal folders.** `BackEnd/integrations/google_drive_deal_folders.gs` replaces the undeployed `google_drive_rehab_summaries.gs`. It runs as you and has three actions, each HMAC-signed with a 5-minute window:
  - `check_folder`: the folder id exists, is a folder, and its owner is the script's account. It answers the folder's name.
  - `save_file`: save `.pdf` / `.csv` / `.html` into `<folder id>/<one subfolder>`, creating the subfolder. The subfolder is `Rehab` or a `YYYY-MM-DD` date, nothing else.
  - Never read, list or delete.

  Env: `DEAL_DRIVE_FOLDERS_UPLOAD_URL` and `DEAL_DRIVE_FOLDERS_UPLOAD_SECRET`. These replace `REHAB_SUMMARY_DRIVE_UPLOAD_*`.
- **The link:**
  - Accepted forms: `https://drive.google.com/drive/folders/<id>` (also `/drive/u/<n>/folders/<id>`, with or without `?usp=…`). The backend keeps the folder id.
  - Saving a Bought deal, or moving one to Bought, checks the format. When the script is configured, it also asks the script to confirm the folder exists and is yours. A file link, someone else's folder, or a deleted folder is refused with a clear message.
- **Move to Bought:**
  - the dialog asks for the Drive folder link, showing the current one if the My Deals deal already has it;
  - the server refuses a move without a valid link (422);
  - MCP `move_to_bought` takes it too.
- **Existing Bought deals without a link** keep working. Their card shows "Add the Drive folder". The rehab summary's Drive channel and HTML to Drive say "add the deal's Google Drive folder first" until it's filled.
- **Rehab summary:** the Drive channel saves the PDF and CSV in `<deal folder>/Rehab/`. The e-mail is unchanged (`REHAB_SUMMARY_EMAIL`).
- **HTML to Drive:**
  - `POST /bought-deals/{id}/projection-to-drive` builds the same HTML as the report download, from the saved deal.
  - It saves the file in `<deal folder>/<today YYYY-MM-DD>/deal projection.html` and answers the folder link.
  - A button on the Bought deal card and in the deal's modal.
  - Same-day saves add another file in that date folder (Drive allows two files with one name).

## Todo
### Step 0: Setup (15 min)
- [x] Commit this plan on the branch (15 min)

### Step 1: The deal-folder Apps Script and its client (2 h)
- [ ] `google_drive_deal_folders.gs`: `check_folder` and `save_file`, an owner check, a subfolder allow-list (`Rehab` or a date), an extension allow-list (`.pdf .csv .html`), a 20 MB cap, constant-time HMAC (1 h)
- [ ] `BL/common/deal_drive_folder.py`: `drive_folder_id_from_link`, `check_deal_drive_folder`, `save_file_to_deal_drive_folder`. Remove `rehab_summary_google_drive.py` and the old `.gs` (1 h)

### Step 2: The required link at Move to Bought (2.5 h)
- [ ] Backend:
  - `move_to_bought` takes `google_drive_link` (body);
  - format check, then the folder check when configured;
  - a Bought deal save validates the link the same way (only when it changed);
  - the link is stored on the new Bought deal (1 h).
- [ ] Frontend: Move to Bought (card and modal) opens a small dialog with the link field, prefilled from the deal, with inline errors; the Bought deal modal shows the same validation (1 h)
- [ ] MCP: `move_to_bought` description and schema mention the required link (30 min)

### Step 3: Rehab summary into `<deal folder>/Rehab` (1 h)
- [ ] The delivery's Drive channel uses the deal's folder id. A missing link is a failure with a clear type (`DealDriveFolderMissing`), retried, and the card says "add the Drive folder". Drop `drive_folder_url` from the old shared tree and answer the deal folder's link (1 h)

### Step 4: HTML to Drive (2 h)
- [ ] Backend route plus BL: build the HTML report from the saved Bought deal (BRRRR and FLIP), then save it to `<date>/deal projection.html`. 404 / 409 (no folder) / 502 (Drive). Audited (1 h)
- [ ] Frontend: an "HTML to Drive" button on the Bought card and in the modal; it shows "Saved to Drive (open folder)" or the error (45 min)
- [ ] MCP tool `save_bought_deal_projection_to_drive` (open-world) (15 min)

### Step 5: Security (45 min)
- [ ] `.claude/security.md`: "Please check through all the code you just wrote and make sure it follows security best practices. make sure there are no sensitive information in the frontend and there are no vulnerabilities that can be exploited throughout all the code in this repo". Concretely:
  - the folder id is pattern-checked;
  - the script writes only into folders you own, into one allow-listed subfolder, with allow-listed extensions;
  - signatures cover the action, the folder id, the subfolder, the file name and the hash;
  - no Drive or script text is relayed;
  - the routes sit behind the data gate.

  Record the result in `SECURITY_PLAN.md` (45 min)

### Step 6: Docs, PR (30 min)
- [ ] README (deal folders, env vars, owner steps); check off this plan; push; open the PR (30 min)

## Tests
- **Unit:**
  - pytest: link parsing (valid, `/u/0/`, `?usp=`, a file link, another host, empty), the signature body, the refusal of a non-Apps-Script URL;
  - vitest: the link validator; the Move to Bought dialog (needs a valid link; prefilled).
- **Integration (pytest):**
  - move to Bought: without a link 422, a bad link 422, a folder the script says isn't yours 422, valid 200 with the link stored;
  - a Bought save with a changed bad link 422;
  - the rehab summary's Drive channel saves into `Rehab` of the deal's folder (fake script), and without a link it fails as `DealDriveFolderMissing`;
  - HTML to Drive saves `deal projection.html` into today's date folder, 409 without a folder, and its HTML equals the report download's;
  - auth gate covers the new route; MCP tools listed and described.
- **E2E:** Move to Bought asks for the link and refuses a bad one; HTML to Drive shows "Saved to Drive" (fake script in the throwaway backend); a close-out summary still delivers.

## MCP
`move_to_bought` takes `google_drive_link`; new `save_bought_deal_projection_to_drive`.

## After merging: your configuration
1. Deploy `google_drive_deal_folders.gs` as a web app under your personal account (execute as me, anyone).
2. On Render, set `DEAL_DRIVE_FOLDERS_UPLOAD_URL`, `DEAL_DRIVE_FOLDERS_UPLOAD_SECRET` and `REHAB_SUMMARY_EMAIL`.
3. Fill the Drive folder link on your current Bought deals.
