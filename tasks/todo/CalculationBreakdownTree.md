# CalculationBreakdownTree: the popup opens on the answer as a table and drills down

Follow-up to PR #74 on branch `claude/epic-hamilton-c1p0rs`. Plan on the branch: `tasks/todo/CalculationBreakdownTree.md`.

## Context

PR #74 renders a section's `CalcStep[]` as a flat list in calculation order, so for the deep sections
(Cash Needed, Cash Out, the wires) the answer is at the bottom after a long scroll and its components
are scattered above it: Cash Needed = Total Cash Invested + Rehab Cushion + Cash to Refi Table, but
"Total Cash Invested (pre-refi)" (itself a 9-term sum) sits several screens up, and its own components
(Cash to Close, Holding Costs, ...) above that. The owner wants it organised as a table.

The breakdown is a tree in disguise: a sum step's terms are either raw inputs or the value of an earlier
step, in the same section or another one (Cash Needed → Total Cash Invested → Cash to Close → HML Points,
where HML Points is filed only under the cash-to-close section). Nothing in the payload links a term to
its step, and label heuristics on the frontend are ambiguous in a dozen places ("Rent" vs "Pre-Refi
Rental Income", "Rehab" vs "Rehab Out-of-Pocket", "Online Notary" in the refi sums vs the "(Buy)" step,
"Cash-Out Wire" vs its "(Lowest ARV)" twin, flip "Closing" vs "Closing × 1.1 buffer", $0 and $5,500
value collisions). So the link is emitted by the backend, where it is known exactly.

**Owner decision (asked):** the popup opens on the answer table with each computed row already expanded
one level; deeper rows open on click; "Expand all" / "Collapse all" in the header.

## Design

### 1. Backend: `CalcTerm.step_label`, derived by object identity (no explain-module edits)

`explain/brrr.py` and `explain/flip.py` read every step value off the frozen results record
(`results.cash_to_close_buy`) and later pass the very same object as a term
(`("Cash to Close (Buy)", results.cash_to_close_buy)`); a frozen-dataclass attribute read returns the
identical `Decimal` object, and no term is an expression (verified over both modules; `results.cash_flow * 12`
only appears in formula text). Raw inputs (`payload.rent`) never are step values; every input and record
field is a `Decimal` (no CPython small-int cache); each `Decimal("0")` is created inline, so $0 steps
("Cash to Refi Table (Lowest ARV)", "Prepaid Interest (Buy)" without a date) link normally: **no non-zero
guard**. Two objects really are shared by two record fields and need a rule: the `ONLINE_NOTARY_FEE`
constant backs both `notary_buy` and `notary_refi` when the fee inputs are left null (`deal_math.py:30`,
`closing_costs_buy.py:28`, `refi_terms.py:52`), and a typed `recordingTransferRefi` / `titleEscrowRefi` is
the same payload object at the ARV and at the lowest ARV (`refi_terms.py:33-34,53-54`). So:

- `ReqRes/common/calc_step.py`: `CalcTerm.step_label: Optional[str] = Field(None, description="When the operand
  is itself a step, that step's label (look it up in this section first, then any section); absent for a raw
  input.")` (the MCP test requires the description). Plain `None` like `note` / `terms`.
- `BL/analyze/common/calc_breakdown.py`: `CalcBreakdown(record=None)`.
  - `__init__` computes `_value_object_ids_backing_two_record_fields` from `vars(record)` (`vars`, not
    `getattr` over `dataclasses.fields`: the `_RecordReads` proxy in `test_explain.py` logs attribute reads,
    and `vars` must not make `TestEveryFieldIsExplained` vacuous); the two explain entry points pass their
    record (`CalcBreakdown(results)`), nothing else in them changes.
  - `add()` registers `id(value) → [(label, frozenset(keys)), ...]` for `Decimal` values, **before** `float()`.
  - `add_sum()` stamps each term with `_linked_step_label(term_value, sum_step_keys)`: a registered step that
    shares a section key with the sum wins; else, if the object backs two record fields, no link; else the
    sole registered label (this keeps flip's cross-section links, e.g. "Total Cash Invested" [roi] → "Total
    Holding Costs" [total_holding_costs], and makes the refi "Online Notary" terms leaves while the buy one
    links to "Online Notary (Buy)").
  - Steps added under several keys are one shared `CalcStep` object, so a label lookup in any section finds
    identical content.
- `mcp_server.py` glossary: one clause on `step_label`. The PDF reads only label/value/sign: unaffected.
- `frontend/src/types/index.ts`: `CalcTerm.step_label?: string | null`.
- Goldens re-recorded once (`cd BackEnd && python3 verify_regression.py snapshot`): `calculations.json`,
  `endpoints.json`, `openapi.json` (`test_mcp.py::test_openapi_contract_is_untouched`), `models.json` if it
  lists `CalcTerm`; `tools/list` stays under its budget (one small `$def` field).

### 2. Frontend: answer-first tree

- `components/deal/calculationBreakdownTree.ts` (pure, unit-tested):
  - `findHeadlineStep(steps, metricValue)` (moved from the popup: last step whose value equals the tile's,
    else the last step).
  - `findStepByLabel(breakdowns, preferredSectionKey, label)`: the term's own section first, then every
    section in order; first match.
  - `rowsOfStep(step, breakdowns, sectionKey)`: a sum step → one row per term
    `{sign, label, value, linkedStep?}` (`linkedStep` from `term.step_label`); a non-sum step → `[]`
    (its formula text is what gets shown).
  - `topLevelRowsForHeadline(...)`: a sum headline → its term rows; a non-sum headline (DSCR, CoC, ROI, flip
    ROI / Annualized ROI) → the section's other steps in order as rows with sign "" and `linkedStep` = the
    step (they are its inputs by construction), shown under the headline's formula.
  - `allExpandablePaths(rows, ...)` for "Expand all", with a cycle guard on the chain of step labels.
- `components/deal/CalculationBreakdownTreeRow.vue` (recursive): a `grid grid-cols-[auto_auto_1fr_auto]`
  row = chevron `<button aria-expanded>` (`pi pi-chevron-down`, rotates when open; `invisible` placeholder
  when the row has no linked step, as `BoughtDealCard.vue:271-275` does) · sign (`+ − =`) · label · value
  (by the step's unit for linked rows, money otherwise). When expanded: one indent level containing either
  the nested rows plus a "= label value" total row (sum step), or the step's `formula` in monospace
  (non-sum step); the step's `note` beneath in muted text. Depth via a `depth` prop → `pl-*`.
- `CalculationBreakdownPopup.vue` keeps the shell (teleport, Escape, focus, inert, header, footer) and now
  takes `breakdowns?: CalcBreakdowns` + `metricKey` + `metricLabel` + `metricValue` (the views pass
  `currentAnalysis?.breakdowns`), on `UiModalPanel size="lg"` (three indent levels need the width). Body, in
  order: the headline's formula card when it is not a sum; the headline's rows as the table, ending on the
  "= {headline} {value}" row; the section's steps *after* the headline (today only "Cash to Refi Table
  (Lowest ARV)" in the lowest-ARV wire section) as rows under a "Derived from this" caption; and a collapsed
  "All N steps" disclosure holding PR #74's flat list, because a non-sum step is a dead end even when its
  formula names another step ("HML Points = 2% × Hard Money Loan"), so e.g. "Purchase Loan (hard money)" is
  otherwise unreachable from the Cash to Close tree. Header gains "Expand all" / "Collapse all"
  (`UiButton variant="ghost" size="sm"`). Expansion state: `expandedRowPaths: Set<string>` (path = indices
  joined by "/"), reset on every open and on a metric change to every depth-1 expandable row.
- The views change only the popup binding (`:breakdowns` instead of `:steps`).

### 3. What the owner sees for Cash Needed

```
How Cash Needed is calculated                                 $59,687.34     [Expand all] [Collapse all] [×]
▾ + Total Cash Invested (pre-refi)                            $37,269.84
      + Earnest Money Deposit                                  $5,000.00
    ▸ + Cash to Close (Buy)                                   $16,386.06
    ▸ + Rehab Out-of-Pocket                                        $0.00
      + HML Interest paid monthly                              $7,986.67
    ▸ + Holding Costs (until refi)                             $2,400.00
    ▸ + Utilities until Rented                                   $240.00
      + Maintenance before Refi                                  $500.00
      + Appliances                                               $630.00
    ▸ − Pre-Refi Rental Income                                 $7,800.00
      = Total Cash Invested (pre-refi)                        $37,269.84
      note: Every dollar actually spent before the refinance; the rehab cushion is held, not spent…
  + Rehab Cushion                                              $5,000.00
▾ + Cash to Refi Table (Lowest ARV)                           $17,417.50
      Wire (-$17,417.50) is negative → $17,417.50 brought to the table
  = Cash Needed                                               $59,687.34
```

## Files

Modify: `BackEnd/ReqRes/common/calc_step.py`, `BackEnd/BL/analyze/common/calc_breakdown.py`,
`BackEnd/tests/test_explain.py`, `BackEnd/tests/_regression_snapshots/*.json` (re-recorded),
`frontend/src/types/index.ts`, `frontend/src/components/deal/CalculationBreakdownPopup.vue` (+ test),
`frontend/src/views/MyDeals.vue`, `frontend/src/views/BoughtDeals.vue` (one binding each), the two view
contract tests (fixtures gain `step_label`), `frontend/README.md`, `README.md` § calculation engine (one
sentence on `step_label`), `mcp_server.py` glossary (one clause).
Create: `frontend/src/components/deal/calculationBreakdownTree.ts` (+ test),
`CalculationBreakdownTreeRow.vue` (+ test), `tasks/todo/CalculationBreakdownTree.md`.

## Tests (rule 3)

- **Unit** — backend `test_explain.py::TestTermsLinkToTheirSourceStep`: over the scenario matrix, every
  `step_label` names an existing step with an equal value; expected links present (BRRRR: Cash Needed →
  "Total Cash Invested (pre-refi)" and "Cash to Refi Table (Lowest ARV)"; Total Cash Invested → "Cash to Close
  (Buy)", "Rehab Out-of-Pocket", "Holding Costs (until refi)", "Utilities until Rented", "Pre-Refi Rental
  Income"; Cash to Close → "Down Payment (cash)", "Closing Costs (Buy)", "HML Points (cash at closing)",
  "Prepaid Interest (Buy)", "Seller Tax Credit"; Cash-Out Wire → "Refi Loan Amount", "HML Payoff at Refi",
  "Closing Costs (Refi)", "Prepaid Interest (Refi)", "Reserves Escrowed at Refi"; Net Profit → "Equity
  (post-refi)", "Cash Out from Deal"; Monthly Cash Flow → "Net Operating Income (NOI)", "Monthly Mortgage
  Payment"; PITIA → "Monthly Mortgage Payment"; Flip: Total Cost Basis → "Rehab Cost (with contingency)" and
  "Closing Costs (Buy)", Net Profit → "Gross Profit", Gross Profit → "Total Cost Basis", Total Cash Invested →
  "Total Holding Costs" (cross-section), Total Cash Needed → "HML Interest (cash, during holding)" while Total
  Holding Costs → "Total HML Interest (over holding period)" (same object, resolved per section), Buffered →
  "Closing × 1.1 buffer"); expected leaves (Rent, the base "Rehab", "Online Notary" in both refi sums, Earnest
  Money Deposit, Rehab Cushion, Construction Budget, HML Interest paid monthly, Taxes ÷ 12, HOA, flip
  "Purchase"); the `typed_overrides` scenario resolves "Recording & Transfer" to the "(Refi)" step in the
  baseline sum and to the "(Refi) (Lowest ARV)" step in the lowest-ARV sum. Plus a `CalcBreakdown` unit test on
  a tiny frozen dataclass: shared object links only inside its section, unshared links across sections,
  `record=None` still works.
  Frontend: `calculationBreakdownTree.test.ts` (own-section-first lookup, cross-section fallback, missing
  label → leaf, non-sum headline rows, expand-all paths, cycle guard); `CalculationBreakdownTreeRow.test.ts`
  (chevron only on linked rows, `aria-expanded`, nested rows + total row, formula for a non-sum step, note,
  sign glyphs, value by unit); `CalculationBreakdownPopup.test.ts` rewritten for the tree (answer rows first,
  depth-1 open by default, click opens deeper, expand/collapse all, non-sum headline shows the formula then
  the section steps, empty state, all the existing shell cases kept).
- **Integration** — the two view contract tests keep their cases with `step_label` in the fixtures and one
  new assertion each: the Cash Flow popup shows NOI's operands (Rent, Operating Expenses) open by default.
  A frontend test loads the re-recorded `BackEnd/tests/_regression_snapshots/calculations.json` by
  `__dirname` (`$.brrr.baseline.body.breakdowns`; precedent: `src/config/brrrInputImpacts.test.ts:10-13`
  reads the repo the same way, and the frontend CI job checks out the whole repo) and asserts the real Cash
  Needed tree resolves Cash Needed → Total Cash Invested (pre-refi) → Cash to Close (Buy) → HML Points (cash
  at closing), and that Rent / Rehab Cushion / Earnest Money Deposit are leaves. No copied fixture: a stale
  golden then fails loudly instead of rotting silently.
- **E2E** — none added (Playwright untouched per the standing instruction); a Playwright smoke by hand on
  Cash Needed and DSCR, screenshots reviewed.

## Todo (≈ 3 h)

- [x] **T1** (5 min) — Plan file on the branch.
- [x] **T2** (20 min) — Backend: `CalcTerm.step_label`, identity registry in `CalcBreakdown`; goldens
  re-recorded; `pytest` green.
- [x] **T3** (20 min) — Backend link tests (present / absent / resolvable).
- [x] **T4** (25 min) — `calculationBreakdownTree.ts` + tests; `CalcTerm` type.
- [x] **T5** (40 min) — `CalculationBreakdownTreeRow.vue` + tests; popup rewritten onto the tree with
  expand/collapse all; view bindings.
- [x] **T6** (25 min) — Popup and view contract tests updated; the recorded-breakdown test.
- [x] **T7** (5 min) — MCP (rule 4): no new endpoint; `step_label` reaches the output schemas through OpenAPI;
  glossary clause; `tools/list` budget checked.
- [x] **T8** (10 min) — Security (`.claude/security.md`): "Please check through all the code you just wrote and
  make sure it follows security best practices. make sure there are no sensitive information in the frontend
  and there are no vulnerabilities that can be exploited throughout all the code in this repo." Expected:
  `step_label` is a label the server already emits, rendered by interpolation; no new inputs, sinks or deps.
- [x] **T9** (15 min) — READMEs; `npm test`, `npm run build`, `pytest`, `verify_regression.py verify`; Playwright
  smoke by hand; PR #74 updated (push to the same branch).

## Verification

1. `cd BackEnd && pytest && python3 verify_regression.py verify` (throwaway Postgres on 55432).
2. `cd frontend && npm test && npm run build`.
3. Smoke: open a BRRRR deal, press Cash Needed: the first screen is the 3-row answer table with Total Cash
   Invested and Cash to Refi Table open; expand Cash to Close → HML Points → its formula; "Collapse all"
   leaves the 3 rows + total; press DSCR: formula on top, PITIA expandable beneath.

## Risks

- A term whose true source is a step but is passed a different object stays a leaf (no wrong link, just no
  drill-down); the link tests enumerate the ones that matter.
- Re-recorded goldens touch three large JSON files; the diff is `step_label` keys only (checked with a one-off
  diff before committing).

## Review

**What changed.** The popup now opens on the answer. `CalculationBreakdownPopup.vue` shows the headline step's
operands as a table ending on the "= headline" line; an operand that is itself a computed step carries a chevron
and expands in place (`CalculationBreakdownTreeRow.vue`, recursive) into its own operands, or into its formula
when it is not a sum, down to the raw inputs. The first level is open on arrival, "Expand all" / "Collapse all"
sit in the header, a headline that is not a sum (DSCR, the returns) shows its formula first with the section's
earlier steps as its inputs beneath, the steps a section derives after its headline follow under "Derived from
this", and a collapsed "All N steps" list keeps the calculation order (a step that is not a sum is otherwise a
dead end even when its formula names another step). `calculationBreakdownTree.ts` holds the pure helpers.

**The link.** `CalcTerm.step_label` names the step an operand is the value of. `CalcBreakdown` derives it from
the identity of the `Decimal` object the explain layer passed: every step value is read off the frozen results
record and passed again, unchanged, as an operand, so `id()` is the link, and no narrative was edited. Two
objects genuinely back two record fields (the default notary fee constant for both legs; a typed refi line
reused at the lowest ARV): a step filed under one of the sum's own sections wins, a shared object stays
unlinked outside those sections, and an unshared object may link across sections (flip's Total Cash Invested
reaches Total Holding Costs). Goldens re-recorded; the diff is `step_label` keys only (446 in
`calculations.json`, 172 in `endpoints.json`, the schema field in `openapi.json` / `models.json`).

**Tests (rule 3).** Backend (+33): every `step_label` names a step carrying the same value, over the scenario
matrix of both engines; the expected links and leaves of the plan (Cash Needed → Total Cash Invested → Cash to
Close → HML Points; Rent, the base Rehab, the refi Online Notary, Earnest Money Deposit, Rehab Cushion,
Construction Budget as leaves; flip's cross-section and per-section links); typed refi lines resolve to their
own variant; a `CalcBreakdown` unit test with a shared object. Frontend (+15 net): `calculationBreakdownTree`
(headline by value, own-section-first lookup, drill-down, expand-all paths, cycle guard, non-sum headline rows,
and the real recorded `calculations.json` resolving three levels deep with Rent / Rehab Cushion / Earnest Money
Deposit as leaves), `CalculationBreakdownTreeRow` (chevron only on computed rows, `aria-expanded` /
`aria-controls`, nested rows + total line + note, formula for a non-sum step, toggle from row and chevron),
`CalculationBreakdownPopup` rewritten (answer rows first, first level open, drill to a formula, expand /
collapse all, reset on reopen, non-sum headline, derived rows, sentinels, all-steps disclosure, empty state,
and the shell cases kept), the two view contract tests on the tree. E2E: none added; a Playwright smoke by hand
on Cash Needed (3 rows → 23 expanded → 3 collapsed), DSCR and the lowest-ARV wire, screenshots reviewed.
Frontend 1489 passed, `vue-tsc` clean; backend 781 passed, `verify_regression.py verify` identical.

**MCP (rule 4).** No new endpoint; `step_label` reaches the output schemas through OpenAPI (golden re-recorded,
`tools/list` budget test green); the glossary names it.

**Security (rule: `.claude/security.md`).** `step_label` is a label the server already emits, rendered through
interpolation only; no new inputs, sinks or dependencies; `npm audit` 0 vulnerabilities.
