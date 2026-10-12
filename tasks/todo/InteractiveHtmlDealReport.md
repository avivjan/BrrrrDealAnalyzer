# InteractiveHtmlDealReport: "Generate Report" produces one self-contained HTML file that works like the popups

Branch: `claude/amazing-rubin-niju54`, restarted from the latest `main` (PR #82 is merged). Plan file: `tasks/todo/InteractiveHtmlDealReport.md`.

## Context
The PDF from PR #82 has the right content, but a PDF can't behave like the website's calculation breakdown popups:
there is no expand/collapse in place, only jump links. You want the same content in a format that is:
- natively clickable, exactly like the popups;
- impressive, beautiful and futuristic;
- easy to send to anyone, including people with no account, by WhatsApp or Gmail;
- openable on iPhone, Mac, Windows, Galaxy and any other device.

**Format: one self-contained `.html` file** (`BigWhales_BRRRR_<address>.html`).
- Every phone and computer opens it with the browser it already has. No app or account is needed.
- WhatsApp sends it as a document. On an iPhone, tapping it opens a preview; on Android, it opens in Chrome or
  Samsung Internet.
- Gmail accepts `.html` attachments; only scripts and executables are blocked.
- Everything is inline: CSS, the logo as an SVG, and system fonts. Nothing loads from the internet, so it works
  offline and never breaks if a link dies. It is about 100–300 KB.

**Works with JavaScript off.** The iPhone preview that opens from WhatsApp and Mail, and the app's own preview frame,
both run with scripts disabled. So the popup's drill-down is built from native `<details>`/`<summary>` elements,
which expand and collapse in place with no script. A tiny inline script only adds extras when it is allowed to run:
"Expand all" / "Collapse all" and a light/dark switch. Without it, the file still works fully.

## Design
### Backend
1. **`BackEnd/BL/reports/common/deal_html_report.py` (new): `build_deal_html_report(address, deal_type, result, selected_result_keys)`.**
   It reuses what the PDF already uses:
   - `breakdown_tree.py`, the Python port pinned to the popup's TS tree by the shared parity fixture;
   - `format_value_like_calculation_popup` and `select_report_result_tiles`.

   It renders with the standard library's `html.escape` and string building, with no new dependency. Every label,
   formula, note and the address is escaped.

   The file's structure:
   - **Header:** the Big Whales mark (inline SVG), the address, a BRRRR/FLIP badge, the generated date, and a
     "Results" grid of glowing value tiles in tile order. Each tile is an anchor link to its section.
   - **One card per chosen result, matching `CalculationBreakdownPopup.vue`:**
     - "How {tile label} is calculated" and the headline value.
     - For a headline that is not a sum, the formula box, its note and "Built from".
     - The tree. Each row shows a chevron, sign, label and value. A row the popup can expand is a `<details>`
       holding its children, recursively down the whole "Expand all" tree, with the same ancestor guard.
     - First-level rows start `open`, as the popup opens on arrival; deeper rows start closed.
     - A child list ends on its "= step" total, or shows the step's formula; the note follows.
     - Then the "= headline" total and the headline note, "Derived from this", and "All N steps in calculation order"
       as a collapsed `<details>`.
     - The footer note, the same as the popup's.
   - **Footer:** the disclaimer and the Big Whales signature, as in the PDF.
   - **Look:**
     - A deep-space dark theme: a near-black navy background, a subtle animated aurora gradient with a faint grid,
       glass cards, and neon cyan/violet accents.
     - Monospace formulas and tabular numbers. Headline values glow.
     - Chevrons rotate when a row opens; every animation respects `prefers-reduced-motion`.
     - Responsive from 320 px phones to desktop, with large tap targets and `<meta viewport>`.
     - A light theme for `prefers-color-scheme: light`, and a clean light layout for printing (`@media print`).
   - **Self-protection:** `<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; img-src data:; script-src 'sha256-<hash of the one inline script>'">`
     The file can run only its own script and can load nothing.
2. **Routes `POST /reports/brrr-html` and `/reports/flip-html`** in `routers/reports.py`.
   - They take the same body, `address`, `selected_result_keys` (validated by the existing
     `_validated_selected_result_keys`, so unknown keys still return 422) and `disposition`.
   - The response is `text/html; charset=utf-8` with
     `Content-Disposition: <disposition>; filename="BigWhales_<TYPE>_<address>.html"`.
   - New BL functions `BL/reports/reportBrrrHtml.py` and `reportFlipHtml.py`, mirroring the PDF ones (validate →
     calculate → build).
   - **The PDF endpoints stay**, so the MCP PDF tools and any old caller keep working. The app no longer calls them.
3. **MCP:** the new routes become the `report_brrr_html` / `report_flip_html` tools automatically. Add their
   `DESCRIPTIONS` entries (under 400 characters each). Check that the MCP response carries the HTML; it is a text
   resource, so check how `mcp_server` returns a `text/html` body and embed it as a resource like the PDF blob.

### Frontend
4. **`api.downloadDealReport(data, type, address, selectedResultKeys)`** calls the `-html` endpoints, with blob
   response and the same params serializer. It replaces the app's use of `downloadDealPdf`.
5. **`useDealReportPdf` becomes `useDealReport`.** It is the same composable with three changes:
   - The filename is `.html`, so `dealReportPdfFilename` becomes `dealReportFilename`.
   - It wraps the response as a `File` with type `text/html`.
   - It adds **`shareFromPreview()`**. Where `navigator.canShare({ files })` is true (iPhone/iPad Safari, Android
     Chrome, Samsung Internet, Mac Safari, Windows Edge/Chrome), it calls `navigator.share({ files: [file], title })`.
     That opens the phone's own share sheet, where WhatsApp and Gmail are one tap away. Elsewhere it falls back to
     the download.
6. **The preview modal (`DealReportPdfPreviewModal.vue` → `DealReportPreviewModal.vue`)** shows the HTML in its
   iframe with `sandbox=""`: no scripts and no navigation out.
   - The rows still expand natively in the preview.
   - The production CSP already allows `blob:` frames.
   - The modal gets three buttons: **Share** (shown only when the device can share files), **Download** (`.html`)
     and Close.
   - The header text changes from "Deal Report Preview" to "Interactive Deal Report".
7. Both views (`MyDeals.vue`, `BoughtDeals.vue`) swap the composable and modal names. The "Generate Report" button
   and the result picker are unchanged.

## Todo (≈ 9 h)
- [ ] **T0** (10 min): Restore the branch on the remote if needed, then commit this plan to
  `tasks/todo/InteractiveHtmlDealReport.md`.
- [ ] **B1** (3 h): Build `deal_html_report.py`, covering the structure, the futuristic CSS, the inline script with
  its CSP hash, the print and light styles, and escaping.
- [ ] **B2** (30 min): Add the `-html` routes, the BL functions and validation.
- [ ] **M1** (30 min): MCP support task: the HTML tools, their descriptions, how the HTML body is returned, and
  their tests.
- [ ] **F1** (1 h 30): Rename the API and composable, add Share with a download fallback, convert the preview modal
  to the sandboxed HTML preview, and wire both views.
- [ ] **V1** (45 min): Render the sample reports in Chromium and WebKit at phone and desktop widths, with
  JavaScript on and off. Take screenshots and polish the design until it looks premium.
- [ ] **G1** (40 min): Re-record the regression goldens (two HTML cases plus the openapi snapshot), the e2e
  `pdf-report*` contracts (now named `deal-report*`), and the audit text strings. Run all suites.
- [ ] **S1** (30 min): Security task, from `.claude/security.md`: *"Please check through all the code you just wrote
  and make sure it follows security best practices. make sure there are no sensitive information in the frontend and
  there are no vulnerabilities that can be exploited throughout all the code in this repo"*. Check:
  - escaping of every text field, with an injection test (`<script>`, `"><img onerror>`, `</style>`);
  - the CSP meta in the file and the sandboxed preview iframe;
  - no external URLs in the file;
  - the filename is still sanitized;
  - bandit, pip-audit and `npm audit` are clean.
- [ ] **P1** (15 min): Tick the plan, push, and update the PR description.

## Tests by layer
**Unit**
- Python (`tests/test_report_html.py`):
  - For every tile of both deal types, the nested `<details>` tree equals the popup's "Expand all" tree, row for row
    and number for number. This reuses the `_expected_outline`-style walk from `test_report_pdf.py`.
  - Only the first level is `open`.
  - Totals, formulas and notes appear where the popup shows them.
  - Escaping, using a malicious label, formula, note and address.
  - The file has no `http(s)://` resource references.
  - The CSP meta hash matches the inline script.
  - The selected keys keep tile order.
- Vitest:
  - `useDealReport`: the `.html` filename, Share calling `navigator.share` with the `File` when `canShare`, and the
    download fallback otherwise.
  - The preview modal: the iframe is sandboxed, and Share is hidden without `canShare`.
  - `api.downloadDealReport`: it hits `-html` with the serialized keys.

**Integration (pytest + TestClient)**
- `POST /reports/brrr-html` and `/flip-html`: the content type, the attachment filename, only the selected sections
  present, and the 422s.
- The MCP `report_brrr_html` call.
- The My Deals and Bought Deals contract tests: Generate leads to an HTML preview, with Share/Download.

**E2E (Playwright)**
- Generate Report: the picker, then the preview iframe shows "How Cash Flow is calculated". Clicking a row inside
  the iframe expands it in place.
- Download offers `BigWhales_BRRRR_…html`.
- **Open the downloaded file in a context with JavaScript disabled** (which simulates the iPhone preview from
  WhatsApp/Mail): the rows still expand and collapse, and the anchor links still jump.
- The same file in the WebKit and Mobile Chrome projects: it renders, there is no horizontal scroll at phone width,
  and the CSP shows no violations.
- Bought Deals: the same flow.

## Verification
- `cd BackEnd && pytest && python verify_regression.py verify`
- `cd frontend && npm test && npx vue-tsc -b && PW_CHROMIUM_PATH=/opt/pw-browsers/chromium npx playwright test --project=chromium`,
  plus the new report specs on WebKit and Mobile Chrome.
- I'll send you a sample `.html` file so you can try it on your own phone: forward it to yourself on WhatsApp, and
  email it from Gmail.
