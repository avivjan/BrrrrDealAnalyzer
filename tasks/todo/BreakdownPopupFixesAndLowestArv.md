# BreakdownPopupFixesAndLowestArv: breakdown popup explanations + Lowest ARV not sticking

Branch `claude/pensive-lovelace-7mdnm5` (harness-designated). Plan file on the branch:
`tasks/todo/BreakdownPopupFixesAndLowestArv.md`.

## Context
You asked for four fixes, mostly in the calculation breakdown popup:
1. **HML Interest paid monthly** (inside *Total Cash Invested*) can't be expanded, so you can't see how it's calculated.
2. **Deed Transfer Tax (Buy)** needs a fuller explanation: who pays it when we pay all closing costs, and who pays it on a standard deal.
3. **Title & Escrow (Buy)**: the line currently reads "Title mode 'we_pay_all' at a $140,000 price → $2,050". It should explain how $2,050 is worked out.
4. **Lowest ARV Possible**: changes reverted at the owner's request; the actual bug is still to be identified.

What I found:
- **(1)** The backend explain layer (`BackEnd/BL/analyze/explain/brrr.py:318`) adds "HML Interest paid monthly" as a sum term. No breakdown step records that value, so the term has `step_label: null` and the popup can't expand it. The value is already calculated as `hml_interest − prepaid_interest_buy − hml_interest_accrued_into_refi_payoff` (`BrrrSteps/hml_and_holding_costs.py:30`), and a `check()` already guards that at `brrr.py:146`.
- **(2), (3)** These are plain formula and note strings at `brrr.py:162-181`. The price tiers live in `BL/analyze/common/deal_math.py` as `TITLE_ESCROW_BUY_WE_PAY_ALL` and `TITLE_ESCROW_BUY_WE_PAY_ALL_TOP`: under $150k → $2,050, $150k to $200k → $2,200, above → $2,400. Standard is $1,000.


Branch: the session requires `claude/pensive-lovelace-7mdnm5`. CLAUDE.md asks for a branch named after the task, but the session rule wins, so all work goes there. Plan file: `tasks/todo/BreakdownPopupFixesAndLowestArv.md`, with checkable items and time estimates.

## Todo (with estimates)
- [x] 1. **Write the plan file** `tasks/todo/BreakdownPopupFixesAndLowestArv.md`, mirroring this plan (5m).
- [x] 4. **Make HML Interest paid monthly expandable** (20m). In `brrr.py`, before the Total Cash Invested sum, add an `add_sum([CASH_NEEDED, "cash_out"], "HML Interest paid monthly", results.hml_interest_paid_monthly, [...])` with these terms:
   - HML Interest (until refi) +
   - Prepaid Interest (Buy) −
   - Accrued Interest (1st of month → payoff) −

   The step also shows the **monthly interest × number of months**, as you asked:
   - Formula line: "Monthly HML interest (per diem $99.67 × 30 = $2,990) × 3.07 months (92 days paid monthly ÷ 30) = $9,169.33". Months are `hml_interest_days_paid_monthly ÷ 30`, which matches the 30-day months the engine already uses.
   - Below it, the expandable rows split HML Interest (until refi) into three parts: prepaid at the buy closing, paid monthly, and accrued into the payoff. The note lists the day counts for each.

   *As built:* a formula step (`breakdown.add`) guarded by `check()` to the cent, not a sum step, because the popup
   shows a sum row's terms but not its formula line. The monthly × months line is the formula, and the split of the
   total HML interest is the note. ~~Originally planned: `breakdown.add(..., terms=[...])`~~ with an explicit `check()`, so the formula text can carry the monthly × months line while the rows stay expandable. No-closing-date case: the prepaid and accrued rows are $0, and all days count as paid monthly. The existing value-identity linking then sets `step_label` on the Total Cash Invested term automatically.
- [x] 5. **Explain the Deed Transfer Tax** (10m). Formula and note in `brrr.py:164`:
   - When we pay all closing costs: "We pay all closing costs → we also take the seller's deed transfer tax: 0.70% × Purchase = …". The note says it is folded into Recording & Transfer (Buy).
   - Standard deal: "Standard deal → the seller pays the deed transfer tax (a seller debit on the settlement statement), so it's $0 to us". The note says switching to 'we pay all' would add 0.70% of the price.
- [x] 6. **Explain the Title & Escrow tier** (15m). In `brrr.py:177`, build the formula from the `deal_math` constants rather than hard-coded text. For example: "We pay all closing costs → title fee by price tier: under $150,000 → $2,050 · $150,000–$200,000 → $2,200 · above $200,000 → $2,400. $140,000 is under $150,000 → $2,050". For a standard deal: "Standard deal → flat $1,000 (buyer's lender-policy share)". Keep the "Formula default … type a value to override" note.
- [x] 7. **MCP server support** (10m). `get_deal`, `analyze_brrr` and the report tools return the backend `breakdowns`, so they pick up the new step and texts automatically. Check through `mcp_server.py` and the MCP tests that nothing pins the old strings. No new tool is needed.
- [x] 8. **Security** (15m), from `.claude/security.md`: review all the code I write for security best practices. Make sure there is no sensitive information in the frontend and no exploitable vulnerabilities anywhere in the repo's changed code. Run the `security-review` skill on the branch diff. *Result: no findings. The new strings are numbers and constants only, rendered escaped by Vue.*
- [x] 9. **Update snapshots and goldens** (15m): `BackEnd/tests/_regression_snapshots/calculations.json` (via `verify_regression.py`), plus any Playwright network goldens the new step changes.
- [ ] 10. **Push the branch and open a PR** (10m).

## Tests
- **Unit (backend, `tests/test_explain.py`)**:
  - The Total Cash Invested term "HML Interest paid monthly" has a `step_label`, and that step's terms add up to the value, with and without a buy closing date.
  - Its formula shows the monthly interest (per diem × 30) × months (days paid monthly ÷ 30), and that product equals the value.
  - The Deed Transfer formula names who pays in both modes.
  - The Title formula lists the tier and the chosen bracket for each of the 3 brackets and for standard.
- **E2E (Playwright)**:
  - The breakdown popup can expand "HML Interest paid monthly" under Total Cash Invested.

## Critical files
- `BackEnd/BL/analyze/explain/brrr.py`
- `BackEnd/BL/analyze/common/deal_math.py` (read the constants only)
- `frontend/e2e/flows/calculation-breakdown-popup-hml-interest.spec.ts`

## Verification
- `pytest BackEnd/tests` against the compose Postgres
- `python BackEnd/verify_regression.py`
- `npm run test` and `npm run build` (type check) in `frontend`
- The Playwright e2e specs above
- Manual check through MCP: `get_deal` on a test deal shows the new expandable step and the new texts
