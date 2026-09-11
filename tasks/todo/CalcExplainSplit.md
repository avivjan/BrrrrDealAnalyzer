# CalcExplainSplit: pure results engine + companion explain layer + readable PDF breakdown

Branch: `claude/pdf-calculation-refactor-rhv25b` (harness-designated). Plan file on the branch:
`tasks/todo/CalcExplainSplit.md`.

## Context

The BRRRR/Flip calculation (`BackEnd/BL/analyze/`) is the most important code in the product, and it is
polluted by the PDF narrative. A `CalcBreakdown` accumulator is threaded positionally through 17 step
functions, each writing 200-450 character f-strings, and several steps **re-implement the math of
`deal_math.py` just to obtain an intermediate for the text**:

- `brrrSteps/cash_out.py:39-40` copies `deal_math.py:51-52` (`total_cash_invested`)
- `brrrSteps/dscr.py:15` copies `calcDSCR` (PITIA)
- `brrrSteps/total_cash_needed.py:80-83` and `flipSteps/total_cash_needed.py:70-73` copy the buffer
  multipliers of `deal_math.py:121-131`

Nothing enforces that the copies stay in sync. `CalcStep` has no unit, so the PDF guesses money vs
percent vs ratio from label text (`deal_pdf.py:183-196`), and the key/label section tables are
duplicated between the results and the PDF. The PDF is the only renderer of `breakdowns`; MCP and the
deal endpoints pass it through as JSON; no Vue component reads it.

**Owner decisions:** (1) pragmatic middle ground: pure math engine returning a frozen dataclass; an
explicit companion `explain_*` function that builds the breakdown from the dataclass and guards every
stated equation at runtime; a CI test that every dataclass field is consumed. (2) Improve wording and
PDF layout in this same task.

**Owner on the regression harness:** not a constraint; change whatever is cleanest and let it fail,
then re-record once at the end. Value equivalence is still proven cheaply: `tests/test_analyze.py`
pins the reference numbers, and a one-off diff of the old vs re-recorded `calculations.json` confirms
`value`, `label` and step order are unchanged while only `formula`/`unit`/`note`/`terms` moved.

## Design

### 1. Pure engine: `compute_brrr_with_intermediates(payload) -> BrrrResultsWithIntermediates`, `compute_flip_with_intermediates(payload) -> FlipResultsWithIntermediates`

- New `BackEnd/BL/analyze/brrr_results_with_intermediates.py`, `flip_results_with_intermediates.py`: `@dataclass(frozen=True)` of every
  **computed** value (dollar basis, intermediates, headline metrics). Inputs stay on `payload`;
  explain receives `(payload, results)`. Deviation from the minimal example (which copies inputs into the
  dataclass): the payload has 30+ inputs that cannot drift; copying them adds noise to the dataclass
  and to the coverage test.
- Step files under `brrrSteps/` and `flipSteps/` keep their names and order (README table stays valid)
  but lose the `breakdown` parameter, every `breakdown.add`, the `_brrr_`/`_flip_` narrative locals
  and the `fmt_*` imports. They return values only, including intermediates that today exist only for
  the text (NOI, PITIA, total_cash_invested, rehab_cash, refi_shortfall, the four buffer components,
  monthly HML interest, monthly operating, contingency, ...).
- `deal_math.py` exposes what it hides, computed once:
  - new `calc_total_cash_invested(...)`, called inside `calc_cash_out_from_deal`
  - new `calc_pitia(mortgage, taxes, insurance, hoa)`, called inside `calcDSCR`
  - `get_total_cash_needed_for_deal` returns a `TotalCashNeeded` NamedTuple (`without_buffer`,
    `with_buffer`, `rehab_cash`, `rehab_float`, `buffered_closing`, `buffered_holding`,
    `buffered_interest`); the two step callers unpack by name. (`verify_regression.py:1061-1066`
    records this helper's raw output, so that golden changes shape; re-recorded at the end.)
    Expression order unchanged so Decimal results are bit-identical (the buffered total groups
    `rehab_cash + rehab_float`; keep it).
- `calculate_brrr_results(payload)` keeps signature and return type (callers in
  `BL/common/deal_response.py`, `BL/reports/reportBrrrPdf.py`, `routers/analyze.py` untouched):
  `results = compute_brrr_with_intermediates(payload); return analyzeBRRRRes(..., breakdowns=explain_brrr(payload, results))`.

### 2. Companion explain layer: `BackEnd/BL/analyze/explain/brrr.py`, `explain/flip.py`

- `explain_brrr(payload, results) -> dict[str, list[dict]]`, reusing `CalcBreakdown` and
  `fmt_money/fmt_pct/fmt_num` from `common/calc_breakdown.py`. Reads only from `results_w_intermediates.` and `payload.`;
  holds no arithmetic except guards.
- **Drift guards.** A `_check(cond, name)` raising `CalcExplainMismatch(ValueError)` (not `assert`,
  which `python -O` strips). Sum-type steps go through one helper that is guard + text + structure at
  once (commit 2 adds the last two):
  ```python
  sum_step(bd, keys, label, total, terms=[("Down Payment", dp), ("Closing", cc, "-"), ...], unit, note)
  # checks sum(±value) == total, renders "Down Payment ($x) − Closing ($y) = $t", stores terms
  ```
  Non-sum steps (mortgage amortization, per-diem interest, DSCR division, ROI/CoC sentinels) guard by
  calling the same `deal_math` helper, or are free text with no guard where no equation is stated.
- Section tables move here as the single definition: `BRRR_SECTIONS` / `FLIP_SECTIONS` =
  `[(key, label, unit), ...]`; `deal_pdf.py` derives both its summary table and its breakdown order
  from them (deletes `_BRRR_SUMMARY`, `_FLIP_SUMMARY`, `_BRRR_BREAKDOWN_ORDER`, `_FLIP_BREAKDOWN_ORDER`).

### 3. Schema and wording (commit 2, additive)

- `ReqRes/common/calc_step.py`: `unit: Literal["money","pct","ratio"] = "money"`,
  `note: Optional[str] = None` (the "— kept on hand for draws..." asides leave the formula),
  `terms: Optional[list[CalcTerm]] = None` with `CalcTerm(label, value, sign)`, only on sum-type steps.
  Every new field gets a `Field(description=...)` (the MCP test
  `test_every_output_field_has_a_description` requires it; `outputSchema` picks them up from OpenAPI).
- Formula text regenerated uniformly by `sum_step` (consistent `+ − × ÷ =` glyphs, `$` money,
  `%` percents). **Labels stay unchanged** so `tests/test_analyze.py` label matching is untouched.
- `frontend/src/types/index.ts`: optional `unit`, `note`, `terms` on `CalcStep`; no UI change.

### 4. PDF layout (commit 2), `BL/reports/common/deal_pdf.py`

- Value column formatted by `step.unit` (drop `_BREAKDOWN_PCT_LABELS`/`_BREAKDOWN_RATIO_LABELS`).
- Sum-type steps render their `terms` stacked, one per line with the sign in front and the total in
  bold, instead of a 450-character wrapped sentence; other steps render `formula` as today.
- `note` rendered under the formula in the small muted style.
- Section heading shows the headline value: "Cash Flow · $85.04/mo".
- Keep brand palette, header, footer, disclaimer as is.

### 5. CI safety net, `BackEnd/tests/test_explain.py`

- **Every field consumed:** a recording proxy (`__getattr__` logs reads) around the dataclass. The
  assertion is on the **union** of reads across a fixed scenario matrix, not per scenario, so a field
  that only one branch explains never produces a false failure. Matrix (each scenario is a payload
  fixture in the test file):
  - BRRRR: `use_HM_for_rehab` × {True, False}; refi wire {surplus, shortfall}; cash flow
    {positive, negative or zero} (drives the ROI/CoC sentinel branches); cash out {≥ 0, < 0};
    interest rate {>0, 0} (mortgage straight-line branch); PITIA 0 (DSCR undefined).
  - Flip: `use_HM_for_rehab` × {True, False}; gross profit {> 0, ≤ 0} (capital-gains branch);
    total cash invested {> 0, 0} with net profit {> 0, < 0, 0} (ROI sentinels); holding months
    {> 0, 0} (annualized ROI branch).
  A second, per-scenario assertion checks that every step **emitted** in that scenario reads its
  value from a field (no explain-side arithmetic), which is branch-safe.
- **Every step value is a dataclass field** (no value computed in explain).
- **Guards fire:** `dataclasses.replace(results, net_operating_income=+1)` raises `CalcExplainMismatch`.
- **Units:** every step has a unit; ROI/CoC/Annualized ROI are `pct`, DSCR is `ratio`, rest `money`;
  `_breakdown_value` formats by unit. **Terms** sum to the step value for every sum-type step.
- **PDF content:** `pypdf` added to the test block of `requirements.txt`; one test per deal type
  extracts text and asserts a section heading with its headline value, a stacked term line and a note.
- Integration: existing `test_analyze.py`, `test_deal_crud.py::TestDealReportPdf`, `test_deals.py`,
  `test_mcp*.py` unchanged and green. E2E: `frontend/e2e/flows/pdf-report.spec.ts` unchanged; its
  golden `e2e/golden/pdf-report.json` re-recorded in commit 2 (formula/unit/note/terms only).

### Edge cases and drawbacks found while reading (owner asked)

1. `assert` is stripped under `python -O`: explicit raise instead.
2. Quantization: `deal_math.py` never rounds or quantizes; every value is a raw 28-digit Decimal until
   `CalcBreakdown.add` converts to `float` and the formatters round for display. So the guards run on
   the dataclass Decimals **before** any float conversion, with operands in the results's order
   (`sum()` of Decimals from int 0 is exact), and use plain `==` with no tolerance. The only float-side
   comparison is the test that JSON `terms` add up to the JSON `value`, which uses `pytest.approx`
   because both sides are already floats. If a guard ever "needs" tolerance, the guard's expression
   order is wrong and gets fixed, not loosened.
3. A drift raises a 500 on that request (intended loud failure); the error message carries the step name
   only, never payload values. Cost is ~30 Decimal comparisons per request.
4. `verify_regression.py verify` is red from C2 until the re-record in C10 (owner accepted).
5. `terms` grows the JSON of `get_active_deals`/`get_bought_deals` (already flagged "very large" in the
   MCP docs) and of `GET /deals/{id}`; kept strictly to sum-type steps (about 12 of ~30 steps per
   deal). Compact `/deals` rows never carried breakdowns. C10 measures one `get_deal` response before
   and after and reports the delta in the PR; `tests/test_mcp.py` already caps `tools/list` at 200 kB
   (currently 174 kB) and the added `CalcTerm` `$def` is a few hundred bytes.
6. `CalcStep.value` stays `float`; `calc_mortgage_payment` keeps raising `HTTPException`. Pre-existing.
7. The explain modules are as long as today's narrative, but linear, read-only and math-free; the
   engine files shrink to a few lines each.

## Files

Modify: `BackEnd/BL/analyze/common/deal_math.py`; `brrrSteps/*.py` (12), `flipSteps/*.py` (8);
`analyzeBRRR.py`, `analyzeFlip.py`; `common/calc_breakdown.py` (`add` gains unit/note/terms,
`sum_step`, `_check`); `ReqRes/common/calc_step.py`; `BL/reports/common/deal_pdf.py`;
`frontend/src/types/index.ts`; `BackEnd/requirements.txt` (pypdf, test block); `README.md`
§"The calculation engine", `BackEnd/README.md:78-79`; `mcp_server.py` glossary (one line on `unit`).
Create: `BackEnd/BL/analyze/brrr_results_with_intermediates.py`, `flip_results_with_intermediates.py`, `explain/__init__.py`, `explain/brrr.py`,
`explain/flip.py`, `BackEnd/tests/test_explain.py`, `tasks/todo/CalcExplainSplit.md`.
Re-record (commit 2 only): `BackEnd/tests/_regression_snapshots/*`, `frontend/e2e/golden/pdf-report.json`.

## Todo (agent wall-clock, ≈ 4 h 45)

Restructure (commit 1; `pytest tests/test_analyze.py` green throughout, goldens may be red):
- [x] **C1** (10 min) — Plan file `tasks/todo/CalcExplainSplit.md` on the branch.
- [x] **C2** (20 min) — `deal_math.py`: `calc_total_cash_invested`, `calc_pitia`,
  `TotalCashNeeded` NamedTuple.
- [x] **C3** (35 min) — BRRRR engine: `BrrrResultsWithIntermediates`, 12 pure steps, `compute_brrr_with_intermediates`.
- [x] **C4** (30 min) — `explain/brrr.py`: moved `add` calls reading from `results`, `_check` guards.
- [x] **C5** (25 min) — Flip engine: `FlipResultsWithIntermediates`, 8 pure steps, `compute_flip_with_intermediates`.
- [x] **C6** (25 min) — `explain/flip.py` with guards.

Wording + layout (commit 2):
- [x] **C7** (30 min) — `CalcStep` fields with descriptions, `sum_step` (guard + text + terms),
  explain modules rewritten onto it, notes split out, `*_SECTIONS` tables; frontend types.
- [x] **C8** (30 min) — `deal_pdf.py`: unit-driven values, stacked terms, notes, headline in section
  heading, sections derived from `*_SECTIONS`; render both PDFs locally and eyeball them.
- [x] **C9** (35 min) — `tests/test_explain.py` (coverage proxy, value-is-a-field, guard fires, units,
  terms reconcile) and the two pypdf content tests (rule 3: unit + integration; E2E golden re-recorded).
- [x] **C10** (20 min) — Re-record goldens; one-off script diffs old vs new `calculations.json` and
  `pdf-report.json` and asserts only `formula`/`unit`/`note`/`terms` keys changed; measure one
  `get_deal` JSON size before/after for the PR description.
- [x] **C11** (10 min) — MCP (rule 4): no new endpoint; `outputSchema` gains the new `CalcStep` fields
  automatically; add the `unit` line to the glossary; `test_mcp*.py` green.
- [x] **C12** (10 min) — READMEs and docstrings: engine vs explain layer; how to add a metric (engine
  field, explain step, the coverage test tells you if you forgot).
- [x] **C13** (5 min) — Security task (`.claude/security.md`): "Please check through all the code you
  just wrote and make sure it follows security best practices. make sure there are no sensitive
  information in the frontend and there are no vulnerabilities that can be exploited throughout all the
  code in this repo." Expected: no new inputs or endpoints, no secrets; guard errors never echo payload
  data; `pypdf` is test-only.
- [x] **C14** (15 min) — Full `pytest`, `verify_regression.py verify`, `npm test`, `npm run build`;
  commit, push, PR.

## Verification

1. `cd BackEnd && pytest` green at every step, including the pinned reference numbers in
   `tests/test_analyze.py` and the new `tests/test_explain.py`.
2. After the re-record (C10): the diff script over old vs new `calculations.json` and
   `pdf-report.json` reports only formula/unit/note/terms changes and the `TotalCashNeeded` helper
   shape; `verify_regression.py verify` green again; `npm test` and `npm run build` green.
3. Manual: `POST /reports/brrr-pdf` and `/reports/flip-pdf` (app, or the `report_brrr_pdf` /
   `report_flip_pdf` MCP tools) and read the breakdown pages: stacked terms, notes, unit-correct values.
4. Both suites need the throwaway Postgres from `BackEnd/docker-compose.test.yml`; if Docker is not
   available in this sandbox, report which checks ran and which did not.

## Review

**What changed.** The calculator is now two layers. `compute_brrr_with_intermediates` / `compute_flip_with_intermediates`
(`BL/analyze/analyzeBRRR.py`, `analyzeFlip.py`) run pure steps and return a frozen `BrrrResultsWithIntermediates` /
`FlipResultsWithIntermediates` record of every number produced (`brrr_results_with_intermediates.py`, `flip_results_with_intermediates.py`); the 20 step files
lost the `breakdown` parameter, every `breakdown.add`, the `_brrr_`/`_flip_` narrative locals and
all string formatting. `deal_math.py` exposes what it used to hide (`calc_pitia`,
`calc_total_cash_invested`, `OperatingExpenses` and `TotalCashNeeded` NamedTuples), so no
intermediate is re-derived for the text. The narrative lives in `BL/analyze/explain/brrr.py` and
`flip.py`: they read the record and the payload, never compute a number, and guard every equation
they state with `check(...)` or the left-to-right fold inside `add_sum(...)`, which raises
`CalcExplainMismatch` (an explicit raise, not `assert`, so it survives `python -O`; the message
names the step only). Sum-type totals in `deal_math.py` are flat left-to-right sums in the order
the explanation lists the terms, which is what lets the guards use exact `==` on unrounded
Decimals with no tolerance.

**Schema (additive).** `CalcStep` gained `unit` (`money` / `pct` / `ratio`), `note`, and, on
sum-type steps, `terms` (`CalcTerm`: label, value, sign); every field is described, so the MCP
output schemas carry them. Labels are unchanged. Three steps were added (BRRRR "Rehab Cost (with
contingency)" and "PITIA", Flip "Monthly Operating Costs") and two sections reordered to read in
calculation order (NOI before the mortgage; cash flow before cash out). A one-off diff against a
12-scenario baseline captured from `main` showed every headline value identical and every old
(label, value) pair still present.

**PDF.** `deal_pdf.py` formats every value by the step's unit (the label-based guessing and the
duplicated key/label tables are gone; `BRRR_SECTIONS` / `FLIP_SECTIONS` in the explain modules
drive both the summary table and the section order), stacks sum-type steps one operand per line
with the total in bold, prints notes under the formula, shows the headline value in each section
heading, keeps headings with their table, and escapes the address (a `<` in an address used to
break the report). The table header text was invisible on the navy band (Paragraph ignores the
row TEXTCOLOR); fixed.

**Tests (rule 3).** `tests/test_explain.py` (+40): every `BrrrResultsWithIntermediates` / `FlipResultsWithIntermediates` field is read by
its explain function across a scenario matrix (hard money vs cash rehab, refi surplus vs
shortfall, positive vs negative cash flow, positive vs negative cash out, 0% loan, PITIA 0, cash
reserve; flip profit vs loss, no cash in with profit / loss / break-even, zero holding time),
asserted on the union of reads so branch-only fields never false-fail; every emitted step value is
a record field; every sum step's terms add up; guards fire on a drifted record and the error
carries no numbers; units are right; the PDF text (read back with `pypdf`) contains the headline
values, a stacked term, a subtracted term, a note and the escaped address. Existing suites
unchanged: backend 317 passed, frontend 1372 passed, `vue-tsc` build green. Backend goldens
re-recorded (`verify_regression.py verify` green); the frontend network-contract goldens that
embed breakdowns were re-recorded with `npm run e2e:record` on chromium.

**Payload growth (owner's watch item).** A single BRRRR analysis response grows from 6.0 kB to
12.0 kB, a Flip one from 5.2 kB to 9.0 kB, all of it `terms` on the 12-14 sum-type steps. Compact
`/deals` rows are unaffected; `get_active_deals` / `get_bought_deals` grow by that much per deal.

**MCP (rule 4).** No new endpoint. `outputSchema` picks up the new `CalcStep` fields from OpenAPI;
the glossary in `mcp_server.py` explains `unit` and `terms`. `tools/list` stays under its 200 kB
budget (`tests/test_mcp.py`).

**Security task (C13).** No new inputs or endpoints; the report recomputes breakdowns from the
validated body and never renders request-supplied breakdown text; the address is now escaped
before reportlab's mini-HTML parser sees it; guard errors never echo deal numbers; `pypdf` is a
test-only dependency; no secrets in the diff (scanned).

**Follow-up worth considering.** With the narrative gone, several step files are one-line
wrappers around `deal_math` helpers; folding them into the orchestrators would remove a layer of
indirection. Left as is here to keep the diff to the plan.
