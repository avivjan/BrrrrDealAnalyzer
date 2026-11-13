# ConstructionAccountsCompactCardsAndRehabSummary: compact construction-account cards, the rehab summary at close-out, loan documents in the owner's Drive

Part A of the branch `ConstructionAccountsCompactCardsAndRehabSummary` (one PR, together with `tasks/todo/MercuryTransferApprovalStatus.md`, which is done first). The branch starts from the latest `main` (`bdff7aa`, with #129 merged).


The Construction Accounts page gets compact cards that open on click, with plain wording. A rehab summary is e-mailed and saved to Drive at close-out. Signed loan documents move to the owner's personal Drive. The doubled account digits are fixed.

## Context

`/liquidity/construction-accounts` (`frontend/src/views/ConstructionAccounts.vue`) shows one big `ConstructionAccountCard.vue` (~450 lines, 12 sections) per deal. One deal fills the screen, the key numbers are inside collapsed `<details>`, and summaries like "Rehab $65,000 of $73,000" don't say what the two numbers are. The owner wants:
1. A short card per property that shows the most important numbers in plain words, so every project fits on one screen. A click opens the full detail, organised and easy to read.
2. At rehab close-out: a summary (every transaction, the draws, the payments, the statistics) e-mailed to the owner and saved to the owner's Google Drive (avivjan2000@gmail.com).
3. Signed loan documents saved to avivjan2000@gmail.com's Drive instead of bigwhalesllc@gmail.com's.
4. A bug fix: "Mercury Checking ••8027 ••8027". Mercury's account name already ends with the last four digits, and the app adds them again.

**Decisions (from the questions):**
- The summary is sent **on close-out**, from both the Close out transfer and Mark closed out. Closed-out cards also get a "Send summary again" button.
- Loan docs: **Drive only.** The script is redeployed under the personal account. The e-mailed signed copies keep their current recipients and sender.

## Workflow (CLAUDE.md)
- One branch and one PR for this plan and `MercuryTransferApprovalStatus.md`.
- Short chat updates after each step. When done: push and open a PR.
- **Privacy:** the personal address is written only in Render env vars (`REHAB_SUMMARY_EMAIL`), never in code, README or the `.gs` headers ("the owner's personal Google account").

## Todo

### Step 0: Setup (15 min)
- [x] Done in Part B: the shared branch exists and both plans are committed

### Step 1: Fix the doubled last-four digits (30 min)
- [x] Add `mercuryAccountDisplayName(account)` to `frontend/src/utils/mercuryAccountDisplayName.ts`. It returns `name ••1234`, or just `name` when the name already ends with those four digits (with or without `••`, `•`, `*` or `x` in front) (15 min)
- [x] Use it in `ConstructionAccountCard.vue` (header), `ConstructionAccountSettingsModal.vue` (both pickers) and `ConstructionAccountSwitchModal.vue` (15 min)

### Step 2: Compact cards and a clearer page (8 h)
- [x] **Pure figures helper** `frontend/src/utils/constructionAccountSummaryFigures.ts`. From a `ConstructionAccountStatus` it computes what the compact card shows (1.5 h):
  - money in the account;
  - lender draws received vs. the lender budget (dollars and a 0–100 % bar);
  - paid to contractors vs. the rehab cost (dollars and a bar);
  - the end outcome: "Back to you at the end $X", or "You need to add $X" when there's a top-up;
  - the most urgent action, e.g. "Deposit $5 due" or "Top-up $1,200 needed".
- [x] **New `ConstructionAccountSummaryCard.vue`**, the closed card, about 2 lines tall (2.5 h):
  - Row 1: the address, the state badge (`constructionAccountStateOf`), the urgent-action chip and a chevron.
  - Row 2, when linked: four labelled figures. "In the account", "Lender draws $A of $B budget" with a bar, "Paid to contractors $C of $D rehab cost" with a bar, and "Back to you at the end".
  - Row 2, when not linked: "Rehab cost $65,000 · Lender budget $73,000 · Under budget: you keep $8,000" and the Link button.
  - The whole card is a `button`, keyboard-accessible and `aria-expanded`. Clicking opens the detail in place, under the card.
- [x] **Restructure `ConstructionAccountCard.vue` as the open detail**, using the existing `UiTabs`. Every editable figure, every action and every `data-testid` hook stays (3 h):
  - **Always visible:** the action bar (Deposit / Steal / Close out) and the error line.
  - **Overview** tab, three plain blocks:
    - "The rehab plan": rehab cost, contingency and lender budget, editable, with "Under budget: you keep $X" or "Over budget: you cover $X".
    - "Your money": your deposit (cushion), deposited so far, still to deposit, taken out so far, the buffer kept.
    - "At the end": back to you, of which your deposit and of which the budget spread, and "Safe to take out now" with the reason for its cap.
  - **Draws & payments** tab: both progress bars with sources, the last draw and payment, paid per payee, and the "before this account" amounts.
  - **Bank transactions** tab: the existing list and its counts.
  - **Entered by hand** tab: the existing list.
  - **Transfers & timeline** tab: the in-app transfers, the limits and the timeline rows.
  - **Account** tab: the linked accounts, settings, switch, mark ready, close out, reopen and unlink; the rehab summary status for closed-out accounts (Step 4).
  - Deep links (`?deal=&open=transactions|manual-entries|…`) open the card and select the matching tab.
- [x] **Plain wording** (1 h):

  | Now | New |
  |---|---|
  | Rehab $65,000 of $73,000 | Rehab cost $65,000 · Lender budget $73,000 |
  | Your own money $5 to deposit | You deposit $5 |
  | Rehab cushion (what you deposit) | Your deposit (cushion) |
  | Spread (budget − rehab cost) | Under budget: you keep / Over budget: you cover |
  | Projected return at rehab end | Back to you when the rehab ends |
  | Safe to steal now | Safe to take out now |
  | Loan draws / Pulled until now | Lender draws received |
  | Rehab paid | Paid to contractors |
  | Pending money in / out | On the way in / out (not settled yet) |
  | Before this account | Paid or drawn before this account existed |

  The long paragraph repeated on every unlinked card is removed; the page header already says it. The KPI labels in `ConstructionAccountTotals.vue` follow the same wording.
- [x] **Page** `ConstructionAccounts.vue`: a list of summary cards. Several can be open at once. A deep link opens and scrolls to its card. Attention cards sort first; closed-out cards go last (30 min).
  - Done, with one addition found in the phone screenshots: the six total tiles became one compact strip, so the first property shows on the first screen. The strip's "Back to you when the rehabs end" adds up the cards' own figure, so the strip and the cards agree.

### Step 3: Rehab summary backend (9 h)
- [ ] **Table** `liquidity_construction_account_rehab_summaries`, a DAL model plus a migration step registered in `runner.py` (1 h). Columns:
  - `id`, `bought_brrr_deal_id` (FK, cascade on delete; also covered in `deleteBoughtDeal.py`);
  - `summary_pdf_bytes`, `summary_transactions_csv_text`, `summary_file_base_name`;
  - `email_delivery_status`, `email_delivery_attempt_count`, `email_last_error_type_name`;
  - `drive_delivery_status`, `drive_delivery_attempt_count`, `drive_last_error_type_name`, `drive_file_id`;
  - `created_at`, `updated_at`.
- [ ] **Content and PDF** `BL/liquidity/constructionAccount/rehab_summary_report.py`. It follows the ReportLab pattern of `BL/inspection/common/inspection_report.py` (`escape`, `escape_attribute`). It builds from `status_of_deal`, the categorised transactions (`_categorised_transactions_of_link`), the manual adjustments and the transfers (3 h):
  - **Statistics:** budget vs. rehab cost, draws received with their count, paid to contractors, under or over budget, your deposit, money taken out, money returned, purchase → rehab completed → close-out dates and days, paid per payee.
  - **Tables:** every bank transaction (date, counterparty, amount, category, override note), the manual entries and the in-app transfers.
  - **A CSV** of every transaction. Cells starting with `= + - @` get a leading `'` (formula-injection guard).
  - The e-mail subject `Rehab completed – <address>`, plus its text and its escaped HTML body.
- [ ] **Drive** (1.5 h):
  - `BL/liquidity/constructionAccount/rehab_summary_google_drive.py`: an HMAC-signed POST, the same as `member_loan_google_drive.py`. It sends the PDF and the CSV into `rehab summaries/<address> (<deal id>)/`.
  - The Apps Script `BackEnd/integrations/google_drive_rehab_summaries.gs`, copied from `google_drive_loan_agreements.gs`: `.pdf` / `.csv` only, a size cap, and only that folder tree.
  - Env vars: `REHAB_SUMMARY_DRIVE_UPLOAD_URL`, `REHAB_SUMMARY_DRIVE_UPLOAD_SECRET`.
- [ ] **Delivery** `BL/liquidity/constructionAccount/rehab_summary_delivery.py`, mirroring `inspection_report_delivery.py` (1.5 h):
  - Recorded in the close-out transaction (`mark_closed_out`), only when `closed_out_at` goes from null to set and never on `preview_only`.
  - Delivered after commit as a background task: the e-mail goes through `deliver_member_loan_email` to `REHAB_SUMMARY_EMAIL`, with the PDF and CSV attached and the sender + `EMAIL_PASSWORD`; the Drive upload runs separately.
  - Each channel is tracked on its own. A failure is retried every 30 min, 3 attempts in all, with the retry loop started from `main.py`. Only error type names are stored.
- [ ] **Endpoints** in `routers/liquidity_construction_accounts.py`, behind the same auth gate (1 h):
  - `GET .../{bought_deal_id}/rehab-summaries`: the delivery statuses.
  - `POST .../{bought_deal_id}/rehab-summaries`: build and send again; closed-out accounts only, at most 10 a day per deal; audited.
  - `GET .../{bought_deal_id}/rehab-summaries/{summary_id}/pdf`: download.
- [ ] Add `rehab_summary_delivery_statuses` (the newest one) to the status response, both in `ReqRes` and in `types/constructionAccount.ts` (30 min)

### Step 4: Rehab summary frontend (1.5 h)
- [ ] API and store methods. On a closed-out card's Account tab and its summary card, show "Rehab summary: e-mailed ✓ · saved to Drive ✓", "sending…" or "will retry", plus the **Download PDF** and **Send again** buttons (1 h)
- [ ] The Close out modal's text says the summary will be e-mailed and saved to Drive (30 min)

### Step 5: Loan documents to the owner's Drive (45 min code + owner step)
- [ ] Code doesn't change. Update the docstring in `member_loan_google_drive.py`, the setup header in `google_drive_loan_agreements.gs` and the README's "Saving signed copies" section: "owned by the owner's personal Google account", and the redeploy steps (30 min)
- [ ] **Owner step (you, ~10 min, guided). This is the "ask the user to add" part:** signed in as avivjan2000@gmail.com, paste **both** scripts (loan agreements and rehab summaries) into script.google.com, set their script-property secrets, and deploy each as a web app. Then on Render, set the new `MEMBER_LOAN_DRIVE_UPLOAD_URL` / `_SECRET`, the `REHAB_SUMMARY_DRIVE_UPLOAD_URL` / `_SECRET`, and `REHAB_SUMMARY_EMAIL=avivjan2000@gmail.com`. I can set the Render env vars through the Render connector if you OK it. Existing PDFs stay in bigwhalesllc's Drive (15 min)

### Step 6: MCP server support (45 min)
- [ ] `mcp_server.py`: tool descriptions for `list_liquidity_construction_account_rehab_summaries` and `send_liquidity_construction_account_rehab_summary_again`. Exclude the binary PDF route, like the photo routes. Update the glossary: a close-out sends the summary. Add the tools to `tests/test_mcp_tools.py` (45 min)

### Step 7: Security (1 h)
- [ ] From `.claude/security.md`: "Please check through all the code you just wrote and make sure it follows security best practices. make sure there are no sensitive information in the frontend and there are no vulnerabilities that can be exploited throughout all the code in this repo". Concretely:
  - no address, secret or token in the frontend bundle or in the repo;
  - every new route is behind the auth gate (the auth-gate test lists them);
  - PDF, e-mail and CSV escaping, including the formula-injection guard;
  - the HMAC signature, timestamp window and folder-tree confinement in the new `.gs`;
  - the send-again rate limit;
  - no Mercury data in logs, only error type names;
  - cascade delete.

  Run `/security-review` on the branch diff and record the results in `SECURITY_PLAN.md` (1 h)

### Step 8: Docs, PR (30 min)
- [ ] README: the Construction accounts section (compact cards, rehab summary, env vars); check off this plan; push; open the PR (30 min)

## Tests

**Unit**
- Vitest:
  - `mercuryAccountDisplayName`: the name already ends with the digits, ends with `••8027`, ends with other digits, has no digits.
  - `constructionAccountSummaryFigures`: not linked, linked, over budget, top-up, closed out, bars clamped to 0–100.
  - `ConstructionAccountSummaryCard`: renders the four figures and emits on click and on Enter.
  - `ConstructionAccountCard`: the tabs, and a deep-link section selecting its tab.
- Pytest:
  - the summary content statistics;
  - the PDF builds, with `<script>` in an address escaped;
  - the CSV formula guard;
  - the Drive request signature and body;
  - the e-mail HTML escaping.

**Integration (pytest, Postgres)**
- Mark closed out records exactly one summary; `preview_only` records none; reopen then close records a second one.
- Delivery with the replaced transports sets both statuses; a failing channel is retried and stops after 3 attempts.
- Send again: 409 while the account isn't closed out, and 429 after 10 a day.
- The new routes are in the auth-gate test, and an unauthenticated call is refused.
- Deleting the Bought deal deletes its summaries.
- The migration step runs twice without changes (`test_migrations.py`).
- `test_mcp_tools.py` includes the new tools.
- `tests/conftest.py` makes sure no test reaches the real SMTP or Drive.

**E2E (Playwright, `frontend/e2e/flows/construction-accounts.spec.ts` + `fake_mercury.py`)**
- With several deals, every compact card is visible without opening any; clicking one opens its tabs; a second click closes it.
- A deep link `?deal=<id>&open=transactions` opens the card on the Bank transactions tab.
- The header shows "Mercury Checking ••8027" once.
- Closing out shows "Rehab summary: e-mailed · saved to Drive" (stub transports in the throwaway backend), and Download PDF answers a PDF.
- Run the a11y spec on the page.

## Verification
- `cd BackEnd && pytest`. Then, in `frontend`: `npm run test`, `npm run build` (types) and `npm run e2e -- --trace off` for the construction-accounts, a11y and navigation specs.
- Run the app (the `run` skill) and take screenshots of the page with 3+ deals, closed and open, at desktop and phone width, to check the layout.
- Manual, after the owner step: close out a test account. The e-mail arrives at the personal address with the PDF and CSV, and both files appear under `rehab summaries/` in that Drive. Sign a test loan document; it lands in the personal Drive's `loan agreements`.

**Total ≈ 23 h**
