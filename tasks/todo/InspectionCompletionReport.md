# Inspection completion report: e-mail plus a Drive folder per inspection (plan)

Task name `InspectionCompletionReport`. The branch is `claude/relaxed-meitner-z0vzc9`: the session's required push branch, restarted from `main` after PR #108 merged. PR to `main` at the end.

## Context

The owner wants every completed property inspection kept and sent to them:
- **Saved:** the finished report is kept as a PDF in Google Drive.
- **E-mailed:** the results go to bigwhalesllc@gmail.com.
- **Organized:** each inspection has its own Drive folder under one parent folder, `inspections`.

Today a completed inspection lives only in Postgres. Photos go to Drive under `property inspections/…`, which is not live yet because the Apps Script hasn't been deployed.

## Decisions (proposed)

| # | Decision |
|---|---|
| D1 | **When.** On every successful `POST /public/inspections/{id}/complete`: the first finish, and "Finish again" after edits. The report is built and delivered in a background task after the commit, so finishing stays instant and a delivery failure never undoes the finish. |
| D2 | **The report is a PDF**, built with reportlab (already a dependency). It holds the start info (address, date, inspector, completed at, any override reason), then Replace items, then Repair items. Each of those items shows its fields, notes and photo thumbnails (from Postgres, so no Drive round trip). Then the windows to replace, the OK items, the items not checked, and the link to the inspection. It contains no deal data. |
| D3 | **The Drive layout** is `inspections/<YYYY-MM-DD> <address> (<id8>)/`, holding the photos and `Inspection report <YYYY-MM-DD HH-MM>.pdf`. Each finish adds a new timestamped report and never overwrites one. The parent folder is renamed from `property inspections` to **`inspections`**, as asked. No photo has been stored under the old name yet, because the script isn't live. |
| D4 | **The e-mail** goes to `INSPECTION_REPORT_EMAIL` (default `bigwhalesllc@gmail.com`) from the company Gmail. It reuses `deliver_member_loan_email` and `EMAIL_PASSWORD`, the same SMTP route as the offer and loan e-mails. Subject: `Inspection completed – <address>`. Body: the counts (Replace, Repair, OK, not checked, windows to replace), the items to fix, a link to the inspection, and a link to its Drive folder. The PDF is attached. |
| D5 | **Reliable delivery.** A new table, `property_inspection_report_deliveries`, holds one row per finish and channel (`email`, `drive`): status, attempt count, the last error type, and the Drive file id. A failed channel is retried up to 3 times, every 30 minutes, by a small production-only background thread in the same style as `member_loan_statement_schedule.py`. A new table needs no migration step, because `create_all` builds it. |
| D6 | **Apps Script** (`google_drive_inspection_photos.gs`): the root becomes `inspections`. A new `save_report` action accepts `.pdf` only, uses the same HMAC and timestamp checks, and returns the file id and the folder URL. The owner pastes the new version before deploying; it isn't deployed yet anyway. |
| D7 | **The UI** shows one line on the finish screen and the summary: "Report e-mailed and saved to Drive", "Sending report…" or "Report will retry". It comes from a new public field, `report_delivery_status`, which reports a status only, never an address or file id. |

## Todo (agent wall-clock)
- [ ] **0** (5 min): Branch from the latest `main` and add this plan.
- [ ] **1** (20 min): The `property_inspection_report_deliveries` model and its CRUD.
- [ ] **2** (60 min): The PDF builder `BL/inspection/common/inspection_report_pdf.py`, with thumbnails.
- [ ] **3** (40 min): Delivery: `inspection_report_delivery.py`, covering the e-mail through `deliver_member_loan_email`, Drive `save_report`, delivery rows, and background-task scheduling from `complete`.
- [ ] **4** (20 min): The retry thread (production only, never under pytest), started from `main.py`.
- [ ] **5** (20 min): The Apps Script: root renamed `inspections`, the `save_report` action, and the folder URL in the answer. The Python client gets `save_inspection_report_to_drive`.
- [ ] **6** (20 min): The frontend status line on the finish screen and the summary.
- [ ] **7** (10 min): **MCP support:** `get_inspection` and `complete_inspection` expose `report_delivery_status`. No new endpoint, so no new tool; update `DESCRIPTIONS` and add a test.
- [ ] **8** (15 min): Regenerate the goldens (`verify_regression.py snapshot`); review the diff.
- [ ] **9** (30 min): **Security task** (from `.claude/security.md`): *"Please check through all the code you just wrote and make sure it follows security best practices. make sure there are no sensitive information in the frontend and there are no vulnerabilities that can be exploited throughout all the code in this repo"*. Specific checks:
  - The e-mail address comes from env only and never reaches a response.
  - The PDF contains user text safely: reportlab paragraphs are escaped.
  - Error text from SMTP or Drive is never stored or returned (type names only).
  - Re-finishing can't be used to spam: a 60/h per-IP limit applies, plus at most 10 reports per inspection per day.
  - Then bandit, pip-audit and npm audit.
- [ ] **10** (15 min): README and `.env.example` (`INSPECTION_REPORT_EMAIL`), the Apps Script steps updated, and the Review section.
- [ ] **11** (10 min): Push, open the PR, CI green.
- [ ] **12** (owner, about 10 min): Deploy the updated Apps Script and set the Render env vars (`INSPECTION_PHOTOS_DRIVE_UPLOAD_URL`, `INSPECTION_PHOTOS_DRIVE_UPLOAD_SECRET`; `EMAIL_PASSWORD` is already set).

## Tests
**Unit (pytest):**
- The PDF builds, and its text holds the address, the Replace and Repair items, the windows count and the override reason, but no deal id.
- HTML in notes is escaped.
- The e-mail subject, body and recipient come from env.
- The `save_report` request signature matches the Apps Script format.
- The Drive folder name and the root are `inspections`.

**Integration (pytest, test Postgres, fake mail and Drive):**
- Completing an inspection e-mails one PDF to the configured address and saves one PDF to Drive, in the same folder its photos use.
- Finishing again sends a second report.
- A failed e-mail or Drive save is recorded and retried (at most 3 attempts), and never undoes the finish.
- Without `EMAIL_PASSWORD` or the Drive settings, the finish still succeeds and the status reads "will retry".
- The public response's `report_delivery_status` carries no address or file id.
- The per-inspection daily report cap is enforced.

**MCP:** `complete_inspection` through the tool triggers the delivery, and `get_inspection` returns the status.

**Frontend (Vitest):** the status line renders each state.

**E2E:** the existing walkthrough flow additionally checks the status line. The backend in E2E has no mail or Drive settings, so it reads "will retry". The golden is updated in a `Golden update:` commit.

## Verification
- Run backend `pytest`, `verify_regression.py verify`, frontend `npm test` and `npm run build`, and the inspection E2E.
- Manual: with `EMAIL_PASSWORD` and the Drive settings pointed at a test script, finish an inspection. Check that the PDF arrives at bigwhalesllc@gmail.com and appears in `inspections/<folder>` next to its photos.
