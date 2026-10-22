# ReportDealInputsSection: a collapsible "Deal Inputs" section in the interactive HTML report

Branch: a **fresh branch `ReportDealInputsSection`** (named per CLAUDE.md), created from a freshly pulled `main`
(`git fetch origin main && git checkout -b ReportDealInputsSection origin/main`). All changes go there, and it gets a
new PR. Plan file on the branch: `tasks/todo/ReportDealInputsSection.md`.

## Context
The interactive report shows how every result is calculated, but not the inputs the deal was built from. You want a
**collapsed section, optional when generating, that lists every input the user entered**:
- dates, numbers and percentages, everything the form holds;
- grouped by the form's **sub-stages**;
- native in the HTML (expands without JavaScript), impressive and beautiful.

Owner decisions:
- **Calculator inputs only.** Notes, contact, task, links and comps stay out of the shared file.
- **"Include deal inputs" starts checked** in the picker.

The sub-stages are the deal form's tabs (`frontend/src/config/dealInputPhaseTabs.ts`):
- BRRRR: **Buy · Rehab · Rent & Holding · Refinance**
- FLIP: **Buy & Rehab · Flip Strategy · Expenses**

The groups inside them follow the section components, for example "Hard Money", "Closing Costs (Buy)", "Closing Costs
(Refi)" and "Reserves escrowed at refi".

## Design
### Backend
1. **New `BackEnd/BL/reports/common/deal_input_sections.py`.** A declarative list per deal type:
   `DealInputSection(tab_key, title, icon) → groups → DealInputField(payload_key, label, display_kind, …)`. It uses the
   form's exact labels, payload keys (aliases) and order, from `brrr/*Section.vue` and the FLIP blocks of
   `DealInputsForm.vue`.
   - **Display kinds and formats**, reusing `format_value_like_calculation_popup` for money and percentages:
     | Kind | Example |
     |---|---|
     | `money` | `$5,000` |
     | `money_thousands` | `purchasePrice` 200 → `$200,000` |
     | `percent` | `75.00%` |
     | `points` | `2 pts` |
     | `days` | `180 days` |
     | `months` | `6 months` |
     | `years` | `30 years` |
     | `date` | `Jan 10, 2026` |
     | `yes_no` | a Yes / No pill |
     | `choice` | `titleModeBuy` → "Standard (lender's policy)" / "We pay all closing costs" |
     | `text` | the other-closing-costs notes |
   - **Formula defaults.** When a field is left blank, it shows the value actually used, taken from the result's
     `*_effective` fields: `recording_transfer_buy_effective`, `title_escrow_buy_effective`,
     `recording_transfer_refi_effective`, `title_escrow_refi_effective`, `vacancy_reserve_effective` and
     `lowest_arv_effective`. The notary fees default to $250, and "Seller already paid this year's taxes" is auto
     (December closing). Each of these gets an **"auto"** chip and a hint naming its formula, like the form's grey
     auto values.
   - **Linked dates as hints.** "Days to Refi: 180 days" with the hint "Refi closing Jul 09, 2026"
     (`refi_closing_date`), and "Until Tenant Occupied" with `tenant_occupied_date`.
   - **Conditional fields, as the form shows them.** A notary fee appears only when the online notary is on. A note
     appears only when it has text. "Seller already paid…" appears only when there is a closing date. The form's
     duplicate Annual Taxes field on the Buy tab is listed once, on its home tab (Rent & Holding), the same as
     `dealInputPhaseTabs.ts`.
   - Deprecated or hidden BRRRR keys (`closingCostsBuy`, `closingCostsRefi`, `cashReserve`, `use_HM_for_rehab`) are
     never listed.
2. **`deal_html_report.build_deal_html_report(..., deal_inputs: dict | None = None)`.** When `deal_inputs` is given,
   it renders one native `<details class="inputs" id="deal-inputs">`, **collapsed**, placed between the result tiles
   and the first card.
   - Summary: "Deal Inputs", the field count, and a chevron. A **"Deal Inputs" chip** in the tiles row links to it.
   - Inside, one **sub-stage panel per tab**: a glass card with an inline-SVG icon (house / wrench / key / refresh;
     house / dollar / wallet for FLIP) and a gradient title. Each panel is its own `<details open>`, so a sub-stage
     can be folded.
   - Each group is a responsive grid of label/value rows: two columns on desktop, one on a phone. Values use
     monospace tabular figures, with chips (auto, Yes/No) and hints underneath.
   - Every text is escaped, as in the rest of the file. No new script; the CSP is unchanged.
   - "Expand everything" opens it too. Print expands it.
3. **BL and routes.** `report_brrr_html` / `report_flip_html` (`BL/reports/report*Html.py`) take
   `include_deal_inputs` and pass `payload.model_dump(by_alias=True)` to the builder. The routes in
   `routers/reports.py` gain `include_deal_inputs: bool = Query(False, description=…)` on both `-html` endpoints.
   - It defaults to false at the API, so existing callers and MCP calls are unchanged. The picker sends true by
     default.
   - The PDF is unchanged.
4. **MCP.** The new query parameter becomes a tool argument automatically. Add a short mention to the two
   `report_*_html` `DESCRIPTIONS` entries (under 400 characters each).

### Frontend
5. **`GenerateReportResultPickerPopup.vue`.** Below the results list, a separated option row "Include deal inputs"
   with the hint "Every value you entered, by stage". It is a native checkbox, **checked on every open**.
   - `generate` emits `(selectedResultKeys, includeDealInputs)`.
   - Generate still needs at least one result.
6. `useDealReport.viewDealReport(deal, type, keys, includeDealInputs)` → `api.downloadDealReport(…, includeDealInputs)`,
   which sends `include_deal_inputs=true` only when it is true.
7. Both views (`MyDeals.vue`, `BoughtDeals.vue`) pass the flag through.

## Todo (≈ 5 h 30)
- [x] **T0** (10 min): Pull the latest `main` and create the fresh branch `ReportDealInputsSection` from it. Check
  that no report or form file changed on `main` in a way that affects this plan. Commit the plan to
  `tasks/todo/ReportDealInputsSection.md`.
- [x] **B1** (1 h 15): `deal_input_sections.py` with every BRRRR and FLIP field: labels, kinds, groups, effective
  values, conditionals and choice labels.
- [x] **B2** (1 h 30): Render the Deal Inputs section in `deal_html_report.py`: markup, CSS (sub-stage panels,
  icons, grid, chips, phone and light/print), and the summary chip.
- [x] **B3** (20 min): Add `include_deal_inputs` through the routes and BL.
- [x] **M1** (15 min): MCP support task: update the tool descriptions and add an MCP test with
  `include_deal_inputs=true`.
- [x] **F1** (45 min): Picker option, composable, API and views, with their tests.
- [x] **V1** (30 min): Screenshots at phone and desktop size, dark and light, JavaScript off. Polish until it looks
  premium.
- [x] **G1** (30 min): Re-record the goldens (openapi, regression report cases, e2e `deal-report*` contracts) and
  run every suite.
- [x] **S1** (20 min): Security task, from `.claude/security.md`: *"Please check through all the code you just wrote
  and make sure it follows security best practices. make sure there are no sensitive information in the frontend and
  there are no vulnerabilities that can be exploited throughout all the code in this repo"*. Check:
  - escaping of every input value, including the two free-text notes, with an injection test;
  - that only calculator inputs are included (no notes, contact or links);
  - bandit, pip-audit and `npm audit`.
- [x] **P1** (15 min): Tick the plan, push, and open the PR.

## Tests by layer
**Unit**
- **The field map matches the form.** Per tab, the backend's numeric field keys equal
  `DEAL_INPUT_FIELD_KEYS_BY_PHASE_TAB` in `dealInputPhaseTabs.ts` (parsed from the file), and the tab titles equal
  `BRRRR_PHASE_TABS` / `FLIP_PHASE_TABS`. No deprecated key is listed.
- **Formatting:** thousands ×1000, percent, points, days, months, years, dates, Yes/No, choice labels, and the auto
  value read from `*_effective`, with its chip.
- **Conditionals:** the notary fee is hidden when the notary is off, a note is hidden when empty, and "Seller
  already paid…" is hidden without a closing date.
- **Escaping:** hostile text in `otherClosingCostsBuyNote` / `otherClosingCostsRefiNote` renders literally.
- **Picker (Vitest):** the option is checked on open and re-checked on reopen, unchecking it emits false, and it is
  emitted together with the keys.
- **Composable and API (Vitest):** `include_deal_inputs=true` is sent only when true.

**Integration (pytest + TestClient)**
- `POST /reports/brrr-html?include_deal_inputs=true` with the conftest payload:
  - the collapsed `details#deal-inputs` is present;
  - its four sub-stage panels are in order;
  - every expected label/value pair matches, e.g. Purchase Price `$200,000`, Closing Date (Buy) `Jan 10, 2026`,
    LTV `75.00%`, and Recording & Transfer showing the effective value with the auto chip.
- The same request without the flag has no inputs section.
- FLIP gets the same checks.
- MCP `report_brrr_html` with `include_deal_inputs`.

**E2E (Playwright, `deal-report.spec.ts`)**
- In the picker, the "Include deal inputs" option is checked. Generate; inside the preview, "Deal Inputs" is
  collapsed, and tapping it shows the Buy / Rehab / Rent & Holding / Refinance panels with the seeded values.
- Unchecked: there is no inputs section, and the request has no `include_deal_inputs`.
- The offline, JavaScript-off phone case: the inputs section opens natively, and nothing scrolls sideways at 390 px.

## Verification
- `cd BackEnd && pytest && python verify_regression.py verify`
- `cd frontend && npm test && npx vue-tsc -b && PW_CHROMIUM_PATH=/opt/pw-browsers/chromium npx playwright test --project=chromium`
  (plus `deal-report.spec.ts` on Mobile Chrome)
- Send you a fresh sample `.html` with the inputs section to try on your phone.

## Implementation notes
- **Branch.** A fresh branch, `ReportDealInputsSection`, created from a freshly pulled `main` (`5806751`, PR #99).
- **Layout.** The section sits at the top of `<main>`: a native `<details id="deal-inputs">`, collapsed. Inside
  it are a stage rail (anchor chips) and one `<details class="stage" open>` per stage. The page header also gets a
  violet "Deal Inputs · View all" tile. "Expand everything" and print open the section too, because the script's
  selector now includes it.
- **Choices made along the way:**
  - The form's Rent & Holding tab is split into "Holding Costs" and "Operating Expenses (% of rent)", so its 12
    values read as groups.
  - FLIP's Capital Gains Tax Rate sits under "Taxes".
- **Fix carried along.** The picker's button still read "Generate PDF" from the last PR. It now reads "Generate
  Report".
- **Security (S1):**
  - Every input value, label and hint is escaped, including the two free-text notes. This is tested with
    `<script>`, `<img onerror>` and `</details>`.
  - Private deal fields (notes, contact, task, niche, links) are never listed. A test sends them in the body and
    checks that they are absent.
  - The file's CSP is unchanged: still one hash-pinned script, which the build re-hashes.
  - bandit (CI flags) is clean.
  - New advisories that would have turned CI's security job red, all fixed in a separate commit:
    - pip-audit: mcp 1.29.1 → 1.30.0, pypdf 6.19.0 → 6.21.1
    - npm audit: follow-redirects 1.16.0 → 1.16.1
- **Results:**
  - Backend: 1118 passed, and `verify_regression.py verify` passes.
  - Vitest: 1672 passed, `vue-tsc -b` is clean, and the build succeeds.
  - Chromium e2e: 118 passed and 4 skipped.
  - `deal-report.spec.ts` on Mobile Chrome: 4/4.
