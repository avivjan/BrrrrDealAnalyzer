# ClickableBreakdownPdfReport: "Generate Report" picks the results, and the PDF reads like the popups

Branch: `claude/amazing-rubin-niju54` (harness-designated; CLAUDE.md's `<task_name>` branch rule is overridden by it,
as in earlier plans). The first commit copies this plan to `tasks/todo/ClickableBreakdownPdfReport.md`.

## Context

Today "View Report" (`MyDeals.vue:733-748`, `BoughtDeals.vue:745-760`) posts the deal to `POST /reports/{brrr,flip}-pdf`.
The PDF is built in `BackEnd/BL/reports/common/deal_pdf.py` (ReportLab), and every section is a flat
Step/Formula/Value table in calculation order. The website's `CalculationBreakdownPopup` is different: it opens on the
answer, and its rows drill down along the `step_label` links the backend stamps
(`calculationBreakdownTree.ts`, `CalculationBreakdownTreeRow.vue`). The owner wants three things:

- The button reads **"Generate Report"**.
- Clicking it opens a **picker popup** that lists every result tile. All of them are checked by default, and the user
  unchecks any they don't want.
- The PDF becomes a **list of the chosen results, each laid out like its popup**: the same numbers, the same tree, and
  the same drill-down.

**Owner decisions (asked and answered):**
- **Clickable** means internal links plus bookmarks. Each result opens like the popup, with the first level expanded.
  Every row that is expandable on the site becomes a link to that step's own block, and each block has a "Back" link.
  The PDF sidebar also gets a nested bookmark outline that mirrors the full tree ("Expand all").
- **Labels** follow the website tiles ("How Cash Flow is calculated"), not the old PDF section labels.

## Design

### Backend

1. **`BL/reports/common/report_result_tiles.py` (new).** It holds `BRRRR_REPORT_RESULT_TILES` (12) and
   `FLIP_REPORT_RESULT_TILES` (7) as `(result_key, tile_label, unit)` in tile order, copied from `MyDeals.vue:1014-1072`.
   The unit comes from `BRRR_SECTIONS` / `FLIP_SECTIONS`. `total_hard_money_cost` has no tile, so it drops out of the report.

2. **`BL/reports/common/breakdown_tree.py` (new).** A one-to-one Python port of `calculationBreakdownTree.ts`:
   - `find_headline_step_index`
   - `find_step_by_label`
   - `is_sum_step`
   - `rows_of_step` (keeps the ancestor-label guard)
   - `rows_of_steps`
   - `top_level_rows_for_headline`
   - `steps_after_headline`

   Each row is a small `CalculationBreakdownRow` dataclass. It computes nothing and only reshapes the engine's steps,
   the same way the TS version does.

3. **`format_value_like_calculation_popup(unit, value)`**, in `deal_pdf.py`. It mirrors `calculationStepFormat.ts`
   exactly and replaces `_money` / `_pct` / `_ratio`. This fixes two divergences so the numbers match the popup
   character for character:
   - Money is never decoded as ∞. Today `_money(-1)` prints "∞".
   - Percentage sentinels read `∞%` / `-∞%`.

4. **`build_deal_pdf(address, deal_type, result, selected_result_keys)` rewritten.** It reuses `_header_block`,
   `_draw_branding` and the styles. The page flow is:
   - **Header** (unchanged).
   - **"Results in this report"**: a summary table of the selected tiles, label and headline value. Each row links to
     its section.
   - **One section per selected result, in tile order, mirroring `CalculationBreakdownPopup.vue`:**
     - Heading "How {tile label} is calculated", then the headline value.
     - A headline that is not a sum gets a formula box, its note, and a "Built from" caption.
     - The tree rows follow, each shown as sign, label and value.
     - Each top-level row that is expandable is printed already expanded, the popup's default state. Its child rows
       are indented beneath it and end on an "= {step label} {value}" total. A step that is not a sum shows its formula
       instead, and any note appears under it.
     - Every expandable row at any depth, including the expanded first level, carries a clickable label. The label
       links to that step's block in the step appendix.
     - After the rows: the "= headline" total row and the headline note.
     - A "Derived from this" block, when the popup has one, uses the same rows.
     - Finally a link "All N steps in calculation order →" points to the per-result steps list in the appendix. This
       stands in for the popup's collapsed `<details>`.
   - **Appendix "Step details"**, with one block per distinct step reachable from the selected results, deduplicated
     by `(section_key, label)`. Each block shows:
     - The step label and value.
     - The step's operand rows, each linked further when expandable, ending on "= total". A step that is not a sum
       shows its formula instead.
     - The note.
     - "← Back to How {tile label} is calculated".
   - **Appendix "All steps in calculation order"**: one list per result, holding every step's label, value, formula
     and note, plus a Back link.
   - **Links and anchors.** Links use ReportLab's `<a href="#…">` / `<a name="…"/>`. Anchor names are generated only
     from indices (`result_3`, `step_17`, `all_steps_3`), never from text.
   - **Bookmarks.** A tiny `_BookmarkAnchorFlowable(bookmark_key, title, level, closed)` calls
     `canv.bookmarkPage` + `canv.addOutlineEntry`. Level 0 is each result, left open. Below it, the popup's full
     "Expand all" tree is nested, each entry pointing at the step's appendix block, closed by default. The ancestor
     guard keeps the tree finite.
   - **Escaping.** Every label, formula and note passes through `xml.sax.saxutils.escape` before it goes into
     Paragraph markup. Today they are not escaped.

5. **Router `routers/reports.py`.** Both routes gain `selected_result_keys: list[str] | None = Query(None)`. When it
   is absent, all tiles are included; this keeps today's callers and the MCP tool working. The key list is validated
   against the deal type's tile list:
   - An unknown key returns 422.
   - Duplicates are collapsed.
   - An empty list returns 422 ("choose at least one result").

   The validated keys pass through `report_brrr_pdf` / `report_flip_pdf` in `BL/reports/*.py` to `build_deal_pdf`.

### Frontend

6. **`components/deal/reportResultTiles.ts` (new).** It holds the same two lists `{ resultKey, tileLabel }`,
   used by the picker.

7. **`components/deal/GenerateReportResultPickerPopup.vue` (new).** It follows the `CalculationBreakdownPopup`
   overlay pattern: Teleport, `z-[60]`, `UiModalPanel size="md"`, Escape, focus restore and `inertOutside`.
   - Props: `open`, `dealType`, `analysis` (for the value shown next to each label).
   - Emits: `generate(selectedResultKeys: string[])`, `close`.
   - Each tile is a native checkbox row, styled like `BoughtDeals.vue:855-870`, with the label and its value
     formatted by `formatCalculationStepValueByUnit`.
   - All boxes are re-checked every time the picker opens. It has "Select all" / "Clear all" controls.
   - "Generate PDF" is disabled when nothing is checked.

8. **`useDealReportPdf.viewDealReport(deal, dealType, selectedResultKeys)`** and
   **`api.downloadDealPdf(..., selectedResultKeys)`**. The call sends `params: { address, selected_result_keys }` with
   `paramsSerializer: { indexes: null }`, which produces repeated `selected_result_keys=a&selected_result_keys=b`, the
   form FastAPI expects.

9. **`MyDeals.vue` and `BoughtDeals.vue`.**
   - The button reads "Generate Report" (while working: "Generating…"), with the tooltip "Generate Deal Report (PDF)".
   - Clicking it opens the picker. The picker's `generate` event closes it and calls `viewDealReport`.
   - `DealReportPdfPreviewModal` is unchanged. Its iframe uses the browser's PDF viewer, which follows internal links
     and shows the outline.

### MCP
- The new query parameter becomes a tool argument automatically (`mcp_server._build_tools`).
- The `DESCRIPTIONS` entries for `report_brrr_pdf` / `report_flip_pdf` in `BackEnd/mcp_server.py:104-113` get a new
  line. It lists the valid keys per deal type, says that absent means all, and says that each result is laid out like
  the site's breakdown popup, with links and bookmarks.

## Files
- **New:**
  - `BackEnd/BL/reports/common/report_result_tiles.py`
  - `BackEnd/BL/reports/common/breakdown_tree.py`
  - `frontend/src/components/deal/reportResultTiles.ts`
  - `frontend/src/components/deal/GenerateReportResultPickerPopup.vue` (+ `.test.ts`)
  - `frontend/src/components/deal/__fixtures__/calculationBreakdownTreeParity.json`
- **Changed:**
  - `BackEnd/BL/reports/common/deal_pdf.py`
  - `BackEnd/BL/reports/reportBrrrPdf.py`, `reportFlipPdf.py`
  - `BackEnd/routers/reports.py`
  - `BackEnd/mcp_server.py`
  - `frontend/src/api/index.ts`
  - `frontend/src/composables/useDealReportPdf.ts`
  - `frontend/src/views/MyDeals.vue`, `BoughtDeals.vue`
- **Goldens:**
  - `BackEnd/tests/_regression_snapshots/openapi.json`
  - `BackEnd/verify_regression.py`
  - `frontend/e2e/golden/pdf-report*.json`
  - `frontend/scripts/audit/golden/text.json`

## Todo (≈ 9 h 30)
- [x] **T0** (10 min): Commit the plan file to `tasks/todo/ClickableBreakdownPdfReport.md`.
- [x] **B1** (20 min): Create `report_result_tiles.py` and pin it to `FRONTEND_*_RESULT_TILE_KEYS` in `test_explain.py`.
- [x] **B2** (60 min): Port the tree helpers to `breakdown_tree.py`, with unit tests that mirror `calculationBreakdownTree.test.ts`.
- [x] **B3** (30 min): Add the shared parity fixture (breakdowns + expected rows for the conftest BRRRR and flip
  payloads, generated once by a small script documented in the fixture). Add a Python test and a Vitest test that both
  build the tree from it and must match.
- [x] **B4** (20 min): Add `format_value_like_calculation_popup`, with parity cases matching `calculationStepFormat.test.ts`.
- [x] **B5** (2 h 30): Rewrite `build_deal_pdf`: summary, popup-shaped sections, step appendix, all-steps appendix,
  links, bookmark outline and escaping.
- [x] **B6** (30 min): Add `selected_result_keys` to the router and the BL, with validation (422s).
- [x] **F1** (15 min): Create `reportResultTiles.ts`, and add a contract test that it matches the tiles the views render.
- [x] **F2** (75 min): Build `GenerateReportResultPickerPopup.vue` and its tests.
- [x] **F3** (20 min): Pass the selected keys through `api.downloadDealPdf` and `useDealReportPdf`.
- [x] **F4** (40 min): Wire both views and rename the button to "Generate Report"; update the existing view-report
  contract tests.
- [x] **M1** (20 min): MCP task: update the `DESCRIPTIONS` entries and add an MCP test that calls `report_brrr_pdf`
  with `selected_result_keys`.
- [x] **G1** (30 min): Re-record the goldens (openapi snapshot, `verify_regression`, e2e `pdf-report*`, audit
  `text.json`) and run the full backend, Vitest and Playwright suites.
- [x] **S1** (30 min): Security task, from `.claude/security.md`: *"Please check through all the code you just
  wrote and make sure it follows security best practices. make sure there are no sensitive information in the frontend
  and there are no vulnerabilities that can be exploited throughout all the code in this repo"*. Check each of:
  - Key allow-list validation and the empty/unknown-key 422s.
  - All PDF markup escaped (a label, formula or note containing `<b>` or `&` renders literally).
  - Anchor names built from indices only.
  - Address escaping kept, and the `Content-Disposition` filename is still sanitized.
  - No secrets or env in the new frontend files.
  - bandit, pip-audit and `npm audit` clean.
  - Review the diff against the rest of the repo's report path.
- [x] **P1** (15 min): Push, open the PR, and tick this plan.

## Tests by layer
**Unit**
- Python:
  - The `breakdown_tree` helpers: headline pick, sum vs non-sum, the ancestor cycle guard, cross-section `step_label`
    lookup.
  - The formatter: money -1 is "-$1", pct -1 is "∞%", ratio "1.20x".
  - The tile lists match the frontend keys.
  - Selected-key validation.
- Vitest:
  - `GenerateReportResultPickerPopup`: all checked on open, re-checked on reopen, uncheck/Select all/Clear all,
    Generate disabled when none are checked, emits the keys in tile order, Escape/scrim close, values formatted.
  - `api.downloadDealPdf`: the repeated-query serialization.
  - `useDealReportPdf`: passes the keys through.
- Parity: the same JSON fixture is checked by both the TS and the Python tree builders.

**Integration (pytest + TestClient, pypdf)**
- `POST /reports/brrr-pdf` with no keys: every tile section "How {tile label} is calculated" is present.
- With `selected_result_keys=cash_flow&selected_result_keys=dscr`: only those two sections are present, and the other
  tile headings are absent.
- **Numbers equal the popup.** Build the tree with `breakdown_tree` from the `/analyze/brrr` response for the same
  payload. Every first-level row and child row, as label plus value formatted like the popup, appears in the PDF text.
- **Clickable.**
  - The pages carry `/Link` annotations whose destinations resolve to named destinations that exist.
  - Every expandable row has one.
  - Every step block has a Back link.
  - `PdfReader.outline` is nested, with one top entry per selected result and children that mirror the tree.
- An unknown key returns 422, an empty list returns 422, and a flip key on the BRRRR route returns 422.
- The flip report gets the same checks.
- A label or address containing markup renders literally.
- MCP: `test_mcp_tools` / `test_mcp.py` check that the tool schema has `selected_result_keys` and that a call with one
  key returns a PDF blob containing only that section.
- Vitest view contracts (`MyDeals` / `BoughtDeals`): the button reads "Generate Report", and a click opens the picker
  with everything checked. After one box is unchecked and Generate is pressed, `downloadDealPdf` receives the
  remaining keys and the preview iframe opens.

**E2E (Playwright, `e2e/flows/pdf-report.spec.ts`)**
- Open a deal, click "Generate Report", and check that the picker lists every tile, all checked.
- Press Generate: the iframe `src` is a `blob:` URL, the request contract carries every key, and the download
  filename is unchanged.
- Uncheck two results and generate: the request carries only the remaining keys (golden re-recorded).
- The same run on Bought Deals.

## Verification
- `cd BackEnd && pytest`, then `python verify_regression.py`.
- `cd frontend && npm test && npx vue-tsc --noEmit && npm run e2e`.
- Manual check: generate a BRRRR report in Chromium's viewer. Confirm the first level is expanded like the popup,
  clicking "Total Cash Invested" jumps to its step block, "Back" returns, the sidebar outline opens and closes the tree,
  and the values match the popup opened from the same tile.

## Implementation notes

- **Selecting results.** The picker always sends the keys that are checked. The request sends nothing only when an
  older client or an MCP call omits `selected_result_keys`. The recorded e2e contracts (`pdf-report*.json`) now
  carry the key list. The e2e recorder (`e2e/fixtures/recorder.ts`) keeps every value of a repeated query key,
  joined with commas; before this change it kept only the first.
- **Parity fixture.** `__fixtures__/calculationBreakdownTreeParity.json` is recorded by
  `RECORD_BREAKDOWN_TREE_PARITY=1 pytest tests/test_report_pdf.py` from the calculation goldens.
  `calculationBreakdownTree.test.ts` rebuilds the same trees in TypeScript and requires an exact match, including
  every formatted value.
- **Step deduplication.** Steps in "Step details" are deduplicated by object identity, which is exact because
  `find_step_by_label` returns the response's own dicts. The plan said `(section_key, label)`. A step reached from
  several results links back to each of them.
- **Test ids.** They keep their names (`*.modal.view-report`) so the e2e and audit selectors stay stable; only the
  text changes.
- **Security review (S1).**
  - Result keys are checked against the deal type's tile list before any calculation. An unknown key or an empty
    selection returns 422, and the 422 echoes at most five caller keys, each cut to 40 characters.
  - Every label, formula, note, tile label and the address is escaped before it enters ReportLab markup. A test
    covers `<b>`, `&`, `<a href>` and `<font>`.
  - Link and bookmark destinations are named from indices only. The ancestor guard and the step worklist keep the
    PDF finite.
  - The new frontend files hold no secrets or env reads.
  - bandit (CI flags), pip-audit and `npm audit --omit=dev` are clean. The one Low bandit note is the
    existing `xml.sax.saxutils.escape` import, which only escapes output and never parses XML.
- **Not changed.** `npm run audit` (the UI script/bindings/text goldens) already fails on `main` because of drift
  unrelated to this change (RepsTracker, MyDeals preview lifecycle). Only the two changed strings were updated in
  its goldens.
