# ClosingCostRefinements: notary amount, gov charges formula (with the HML bug), routi label, closing-cost notes

Branch `ClosingCostRefinements` from `main`. Four owner's asks after using #70–#72.

## Context

1. **Online notary** is a checkbox that adds a fixed $250. The fee varies; the owner wants the checkbox
   kept, with an editable amount once checked, $250 by default.
2. **Government recording & transfer (buy)** is `0.55% × purchase loan + $250`. Two problems: the
   percentage must apply to the **whole hard-money loan** (purchase loan + construction budget), not
   the purchase loan alone — a bug; and the **deed transfer tax** is missing: $0 on a standard deal
   (seller's debit) or `0.70% × purchase price` when we pay all closing costs (the title mode).
   New default: `$250 + 0.55% × hml_amount + deed_transfer_tax_buy`.
3. **Label**: "Wire (Lowest ARV)" → "Cash-Out Routi (Lowest ARV)" wherever the conservative wire is shown.
4. **Notes** next to "Other Closing Costs" (buy and refi) to say what the amount is for.

## Design (minimal, follows the lifecycle conventions)

**Inputs** (`ReqRes/common/brrr_lifecycle_inputs.py`, `DAL/data_models/common/brrr_lifecycle.py`,
one row each in `migrations/steps/brrr_lifecycle_columns.py`; all nullable, so the migration is a
plain add and old rows keep today's behaviour):
| Column | Alias | Type | Meaning |
| --- | --- | --- | --- |
| `online_notary_fee_buy` | `onlineNotaryFeeBuy` | NUMERIC(12,2) NULL | null = $250 when the notary checkbox is on |
| `online_notary_fee_refi` | `onlineNotaryFeeRefi` | NUMERIC(12,2) NULL | same, refi |
| `other_closing_costs_buy_note` | `otherClosingCostsBuyNote` | VARCHAR(500) NULL | free text |
| `other_closing_costs_refi_note` | `otherClosingCostsRefiNote` | VARCHAR(500) NULL | free text |

**Engine**
- `closing_costs_buy_step`: `notary_buy = effective(online_notary_fee_buy, 250) if online_notary_buy else 0`;
  `deed_transfer_tax_buy = 0.70% × purchase_price if title_mode_buy == "we_pay_all" else 0`;
  `recording_transfer_buy default = 250 + 0.55% × hml_amount + deed_transfer_tax_buy` (the step
  receives `hml_amount`, no longer `purchase_loan_amount`). `deal_math.recording_transfer_default`
  gains the deed-tax term for the buy leg via a new `recording_transfer_buy_default(hml_amount,
  deed_transfer_tax)`; the refi leg keeps `0.55% × refi loan + 250`.
- `refi_terms_step`: `notary_refi = effective(online_notary_fee_refi, 250) if online_notary_refi else 0`.
- Record + response gain `deed_transfer_tax_buy` (described); explain narrates it and the new
  recording formula; `BuySettlement`/`RefiTerms` keep their shapes.
- Validation: the two fees ≥ 0 (join `_BRRR_NON_NEGATIVE_DOLLARS`); notes ≤ 500 chars (Pydantic).

**Frontend**
- `brrrAutoCalc.ts` mirrors the notary amount, the deed tax and the new recording default (parity
  test numbers move: recording 1130 → 1432.50 on the fixture).
- `BuySection` / `RefinanceSection`: the notary row keeps the checkbox; when checked an
  `AutoDefaultMoneyInput` (computed default 250) sits beside it. "Other Closing Costs" gets a text
  input for the note under it (`ui-input`, placeholder "What is it for?").
- Labels: "Wire (Lowest ARV)" → "Cash-Out Routi (Lowest ARV)" in both modals; the Refinance auto
  figure, the Analyze rail and the (i) impact label follow.
- Types, defaults (`onlineNotaryFeeBuy: null`, notes unset), validation, copy-for-AI, impact map
  (`onlineNotaryFeeBuy/Refi` affect the same outputs as the checkbox; notes affect nothing).

## Todo (≈ 2 h 15)
- [ ] C1 (10 min) Branch + this plan.
- [ ] C2 (25 min) Backend inputs, columns, migration rows; engine (notary amount, deed tax, HML-based
  recording), record + response field, explain, validation.
- [ ] C3 (15 min) Fixtures (`conftest`, `verify_regression`), `test_deal_crud` lists, compact/MCP prose if any.
- [ ] C4 (25 min) Tests — **Unit**: `test_brrr_lifecycle.py` (recording uses `hml_amount` and moves
  with the construction budget; deed tax 0 vs 0.70% by title mode; notary amount default/override/off);
  **Integration**: `test_deal_crud.py` round trip of the four new fields incl. a 500-char note;
  `test_migrations.py` new columns present and NULL; **E2E**: none (Playwright untouched per owner).
- [ ] C5 (25 min) Frontend: types, defaults, validation, `brrrAutoCalc`, sections (notary amount,
  notes), labels, impact map, copy-for-AI.
- [ ] C6 (20 min) Frontend tests: `brrrAutoCalc.test.ts` parity numbers, `DealInputsForm.test.ts`
  (notary amount appears only when checked; note round-trips), impact-map completeness.
- [ ] C7 (5 min) MCP: no new endpoint; the four fields and `deed_transfer_tax_buy` reach the tools
  through OpenAPI; re-record goldens; check the `tools/list` budget.
- [ ] C8 (5 min) Security (`.claude/security.md`): the notes are free text — bounded at 500 chars
  like the other text fields, rendered through Vue interpolation only (no `v-html`), never in the
  PDF; no new secrets or sinks; audits unchanged.
- [ ] C9 (5 min) `pytest`, `verify_regression.py verify`, `npm test`, `npm run build`; push; PR.
