# ConstructionAccountPerRehab: one Mercury construction account per rehab, a Construction Accounts page with manual controls, in-app Deposit and Steal transfers, deal lifespans on the timeline

Branch `ConstructionAccountPerRehab` from the latest `main` (`f10e595`, which already has the deal impact view and recurring occurrence states). The plan is committed first as `tasks/todo/ConstructionAccountPerRehab.md` on that branch; no implementation code until you approve it. Goldens and regression snapshots change only in `Golden update:` commits.

## Context

The liquidity timeline starts from the Mercury balance of the "counted as cash" accounts and assumes every dollar there is free. Construction draws and GC payments are deliberately never rows (`BL/analyze/brrrSteps/cash_needed_schedule.py`): the schedule assumes lender → GC is simultaneous and only the spread ("stolen money") is ours, as one row at rehab completion. When a draw lands in checking before the GC is paid (the $30k case happening now), the timeline shows money that belongs to the GC. The spread inside early draws is then counted a second time by the Stolen money row.

Outcome:
- Each rehab gets its own Mercury construction account, excluded from cash. It can be linked at any stage of the rehab, or switched mid-project.
- A dedicated page manages every such account, with manual controls for when real life diverges from the bank feed.
- The timeline shows one honest number per rehab: what comes back at rehab end, computed live.
- The app moves the money for the bootstrap deposit and for steals, behind a biometric step-up.
- Alongside: deal lifespans drawn on the timeline, a better default range in the import preview, and a flooring reminder at Rehab Cost.

## Decisions (agreed in chat)
1. **One construction account per rehab** at a time, in the LLC that owns the property. The lender wires draws there and rehab payments leave from it. It can be **linked at any stage of a rehab, or switched mid-project**.
2. **Appliances stay as they are today.** They remain their own money-out row on the rehab-completed date, paid from checking. They are not part of rehab actual, the construction account or `original_steal`.
3. **The cushion is a bootstrap deposit into the account**, never counted as "back" on its own. It is part of what returns at rehab end, unless you steal it earlier.
4. **Change orders = edit the Bought deal** (rehab cost, and the construction budget when the lender funds it). The card links to that edit; the existing re-sync preview shows the effect.
5. **Deposits and steals move between the construction account and the same LLC's checking** (same Mercury workspace), so Mercury reports them as internal transfers.
6. **The app performs two transfers:**
   - **Deposit:** checking → construction account; afterwards the deposit row is marked Done and the timeline refreshes.
   - **Steal:** construction account → checking.

   Both go through a write-capable token with the Phase 6 controls. **Top-up stays a timeline reminder row**, not a transfer.
7. **Conservative timing stays:** the deposit is money out on the purchase closing date, the return is money in on the rehab-completed date, and a needed top-up is money out today.
8. **A dedicated Construction Accounts page** (`/liquidity/construction-accounts`). It lists exactly the deals the timeline's deal bar shows (`DealLegendPanel`, fed by `GET /liquidity/deals`) that are Bought BRRRR deals between the purchase closing and an approved refi.
9. **Every automatic number can be corrected by hand, and the page shows where each number comes from.** The bank feed is the default, never the only truth:
   - the before-link baselines are always editable;
   - manual payments and draws made outside the account can be logged;
   - any bank transaction can be ignored or re-categorised.

   The other manual controls are listed under "Manual controls" below.

## The model

```text
loan_draws_pulled =
    bank_draws_sum (non-ignored)
    + loan_draws_pulled_before_construction_account_dollars
    + manual_draw_adjustments_sum

rehab_payments_made =
    bank_rehab_payments_sum (non-ignored)
    + rehab_payments_made_before_construction_account_dollars
    + manual_payment_adjustments_sum

projected_return_at_rehab_end =
    current_construction_account_balance
    + (construction_budget − loan_draws_pulled)
    − (rehab_cost − rehab_payments_made)
```

**How bank transactions are categorised:**
- Automatic categories:
  - external money in = a loan draw;
  - external money out = a rehab payment (a refund coming in, once re-categorised as a rehab payment, counts negative);
  - an internal transfer = own money (a deposit or a steal);
  - failed and cancelled transactions are skipped.
- A per-transaction override can set the category to loan draw / rehab payment / own money, or **ignore** it.
- Ignored and own-money rows are left out of both sums, but they still sit in the balance, so the projection treats them as money that isn't this rehab's draw or payment (for example, materials bought here for another property).
- In-app transfers count as soon as Mercury accepts them. They are matched to the Mercury transaction by its transfer id, so they are never counted twice.

**Manual adjustments** (money that never touched this account, such as a contractor paid from another account, a credit-card material run or cash) add to the sums but don't change the balance.

**Inputs:**
- `rehab_cost` = the deal's actual rehab cost (base + contingency, as the analysis computes it), without appliances.
- `construction_budget` = the deal's construction budget.

**Helpers:**
- `original_steal = construction_budget − rehab_cost`
- `planned_deposit = planned_deposit_override_dollars ?? (rehab_cushion + max(0, −original_steal))`
- `remaining_deposit = max(0, planned_deposit − own_money_transferred_into_the_account)`; 0 once the deposit row is Done
- `safe_to_steal_now = max(0, min(available_balance − minimum_balance_to_keep_in_construction_account_dollars, projected_return_at_rehab_end))`
- The **return row** shows `projected_return_at_rehab_end + remaining_deposit`, because the deposit still to come will land in the balance. Before an account is linked, that is `rehab_cushion + max(0, original_steal)`.

**The rows each BRRRR deal gets** (identity = deal + item key + occurrence 1):

| Item key | When | Amount |
|---|---|---|
| `construction_account_deposit` | money out, purchase closing | `planned_deposit`, then `remaining_deposit` live; Done when the in-app Deposit (or a manual one) brings it to 0 |
| `construction_account_balance_returned_at_rehab_end` | money in, rehab completed | `max(0, projected_return_at_rehab_end + remaining_deposit)`; Done at close-out |
| `construction_account_top_up_needed` | money out, today | only while that sum is negative: its absolute value |

- **Removed from the schedule:** the `rehab_cushion` and `stolen_money` rows. `appliances` stays unchanged.
- `total_cash_needed_for_deal` keeps its value; it still includes the cushion as peak cash committed.
- **The schedule invariant becomes Σ rows = −(total cash needed − rehab cushion)**, because the cushion is the one item that comes back.

## Manual controls

The first three are what you asked for. I propose the rest after reviewing the whole workflow for where the automation can be wrong during a live rehab.

| Control | Why it's needed | Effect |
|---|---|---|
| **Editable baselines** (draws / payments before this account) | linking mid-rehab; correcting a guess later | change the two sums at any time from "Account settings" |
| **Manual payments and draws** (add, edit, delete; date and note) | a contractor paid from another account, a credit-card material run, cash; a draw wired to checking | added to `rehab_payments_made` / `loan_draws_pulled` |
| **Ignore a bank transaction** (with a note) | a mistaken transfer, materials for another property | left out of both sums |
| **Re-categorise a bank transaction** (draw / rehab payment / own money) | a refund that looks like a draw; a deposit from another LLC that looks like a payment; a lender fee | moves it into the right sum, or into own money (which counts toward the deposit) |
| **Deposit target override** | starting with less (or more) than the cushion formula | replaces `planned_deposit`; the deposit row follows |
| **Keep-at-least buffer** in the account | reimbursement draws: the electrician must be paid before the lender reimburses | lowers `safe_to_steal_now`; Steal warns when crossing it |
| **Steal above the safe amount** (confirm) | a deliberate choice to take more now and top up later | allowed after a warning that names the coming top-up |
| **Switch the construction account** | the account is replaced mid-project | the old account's categorised draws and payments are folded into the baselines (prefilled, editable). It's allowed once the old balance is $0 (move it to the new account first). The deposit stays Done, and the old account is kept in the history |
| **Mark ready for close-out** | rehab done but the milestone not approved yet | enables Close out before the rehab-completed approval |
| **Mark closed out without a transfer** / **Reopen** | you emptied the account in Mercury yourself; you closed it by mistake | sets or clears `closed_out_at` and the return row's Done; warns if the balance isn't $0 |
| **Mercury unavailable** (behaviour, not a control) | an outage, or a token problem | rows keep their last amounts, and the page says "amounts as of <time>" |

## Todo

### Phase 0 — Setup (0.75 h)
- [x] Branch `ConstructionAccountPerRehab` from the latest `main`; commit this plan as `tasks/todo/ConstructionAccountPerRehab.md` (15 min)
- [x] **Mercury API check (time-boxed):**
  - the transactions endpoint and its fields (a stable transaction id, `kind` for internal transfers, `status`, signed `amount`, counterparty name, paging);
  - the internal-transfer endpoint (source, destination, amount, idempotency key, and whether Mercury approval policies can leave a transfer pending);
  - the narrowest token type that can create internal transfers.

  If Mercury can't do internal transfers through the API, stop and tell you before building Phase 6 (30 min)

  **Result of the check (2026-11-13).** `docs.mercury.com` is not reachable from the build session, so this comes from search results of Mercury's reference pages and third-party clients, not from reading the pages:
  - transactions: `GET /api/v1/account/{id}/transactions`; `kind` includes `internalTransfer`, `externalTransfer`, `outgoingPayment`, card and wire kinds; `status` is `pending` / `sent` / `cancelled` / `failed`; filters by date range and status;
  - internal transfer: `POST /api/v1/transfer` with `sourceAccountId`, `destinationAccountId`, `amount` (≥ 0.01) and `idempotencyKey`, all required, plus an optional note; both accounts in the same organization. So internal transfers are possible and Phase 6 goes ahead;
  - **not confirmed:** the transfer's response body (id and status fields), whether a repeated idempotency key answers 409, and whether a transfer can come back pending approval. The transfer code treats every one of these defensively, and the first real transfer must be a small one, checked in Mercury.

### Phase 1 — Schedule: deposit and return rows (3.5 h)
- [x] `cash_needed_schedule.py`: replace the `rehab_cushion` and `stolen_money` rows with `construction_account_deposit` and `construction_account_balance_returned_at_rehab_end`; leave `appliances` untouched. Update the catalogue tuple, the docstring and the "never a row" note; pin the rounding target to `−(total_cash_needed − rehab_cushion)` (2 h)
- [x] Explain text, the MCP glossary (`mcp_server.py`, the stolen-money definition), and the labels in `CashNeededScheduleTable.vue` and `DealCashRowChangesList` for the new keys (0.75 h)
- [x] Migration step (`migrations/steps/`, registered in `runner.py`): set `liquidity_rows_out_of_date = true` on every imported BRRRR deal, so each shows Re-sync with the before → after list. No row changes silently (0.75 h)

### Phase 2 — DAL, projection and endpoints (12 h)
- [x] **Tables** (DAL models + one migration step) (3 h):
  - `liquidity_construction_accounts`, one per Bought BRRRR deal:
    - `bought_brrr_deal_id` (unique), `mercury_workspace_label`;
    - `construction_mercury_account_id` (unique), `primary_checking_mercury_account_id`, `previous_construction_mercury_account_ids` (JSON history);
    - `loan_draws_pulled_before_construction_account_dollars`, `rehab_payments_made_before_construction_account_dollars`;
    - `planned_deposit_override_dollars` (nullable), `minimum_balance_to_keep_in_construction_account_dollars` (default 0);
    - `marked_ready_for_close_out_at`, `closed_out_at`, `linked_at`, `updated_at`.
  - `liquidity_construction_account_manual_adjustments`: `id`, `bought_brrr_deal_id`, `adjustment_type` (`manual_payment` / `manual_draw`), `amount_dollars` (> 0), `note`, `date`, `created_at`, `updated_at`.
  - `liquidity_construction_account_transaction_overrides`: `mercury_transaction_id` (unique), `bought_brrr_deal_id`, `ignored` (bool), `category_override` (nullable: `loan_draw` / `rehab_payment` / `own_money`), `note`, `updated_at`.
  - `liquidity_construction_account_transfers`: see Phase 6.
  - Deleting the Bought deal deletes all of its rows (`BL/boughtDeal/deleteBoughtDeal.py`).
- [x] **Link and settings** (2 h):
  - `PUT /liquidity/construction-accounts/{bought_deal_id}` creates or edits the link. Everything stays editable at any time: baselines, checking, deposit target override, keep-at-least buffer.
  - Validation: both accounts are in the same workspace; the checking is counted as cash; the construction account isn't linked to another deal; amounts are ≥ 0.
  - `DELETE` unlinks, after a confirm that names the manual entries and overrides that go with it.
- [x] **Switch account** (1 h): `POST .../switch-account` (body: the new account id, plus the baselines to save). `GET .../switch-account-preview` returns the old account's categorised draws and payments and its balance. A 409 while the old balance isn't $0. On save: the baselines get the confirmed values, the old id moves into the history, and the overrides of the old account's transactions stay stored but are no longer used.
- [x] **Manual adjustments** (1 h): `POST /liquidity/construction-accounts/{bought_deal_id}/manual-adjustments`, `PUT` / `DELETE .../manual-adjustments/{adjustment_id}`. Validation: amount > 0 and under a sane cap, note ≤ 500 characters, a date.
- [x] **Transactions and overrides** (1.5 h):
  - `GET .../transactions` lists the account's transactions: date, counterparty, amount, automatic category, override, effective category.
  - `PUT .../transactions/{mercury_transaction_id}/override` takes `ignored`, `category_override` and `note`. It's refused unless the id is one of that deal's account transactions (checked against the fetched list). `DELETE` restores automatic.
- [x] **Close-out controls** (0.5 h): `POST .../mark-ready-for-close-out`, `POST .../mark-closed-out` (no transfer; the answer says if the balance isn't $0), and `POST .../reopen`.
- [x] `BL/liquidity/mercuryBalance.py`: a linked construction account is never counted as cash, even while `mercury_account_ids_counted_as_cash` is null (0.5 h)
- [x] `mercury_client.py`: `fetch_account_transactions(account_id, since)` with the read token, paged and cached like balances. `GET /account/{id}/transactions` joins `/accounts` as the only read URLs (1 h)
- [x] `BL/liquidity/constructionAccount/construction_account_projection.py` (pure):
  - takes the transactions, overrides, manual adjustments, link settings and the transfer log;
  - returns the model above plus a breakdown of each sum by source (bank / before-link / manual) for the page (1 h)
- [x] Reuse the deal-row machinery: `planned_cash_rows_including_construction_account_live_amounts(deal, projection)` next to `planned_cash_rows_including_late_refi_months` (`deal_cash_rows.py`), so re-sync and refresh agree. Live amounts always win on the three rows; the return row's date can still be postponed (0.5 h)
- [x] `POST /liquidity/construction-accounts/refresh` (body: `today`), called on timeline load next to `refreshLateRefis` (`frontend/src/api/liquidity.ts`), and after every write above.
  - `GET /liquidity/construction-accounts` returns every eligible deal, linked or not, with the page's fields and `amounts_as_of`.
  - If Mercury fails, rows keep their last amounts.
  - Idempotent by identity; every write audited without amounts (0.5 h)


**How Phase 2 was built (2026-11-13), where it differs from the list above:**
- **The link stores the bank sums of the last refresh** (balance, categorised draws, payments, own money in / out, `bank_amounts_as_of`) and the two accounts' names with their last four digits. Every number is recomputed from those without Mercury, so a deal save, a re-sync and an outage all see the same three rows, and `GET /liquidity/construction-accounts` never calls Mercury.
- **A change order waits for the Re-sync.** A deal that is "liquidity out of date" keeps its three rows until you confirm the re-sync (which aims for the live amounts). The page shows the new projection at once and says the rows are waiting.
- **Marked done, not deleted.** The deposit row is marked Done when your own money in the account reaches the deposit target; the return row is marked Done at close-out.
- **Unlink** puts the three rows back on the schedule's plan.
- **Editing a link** uses the same `PUT`; changing the construction account itself is only the switch.
- **The MCP descriptions and annotations of these 15 tools are done here** (the tests require them with the routes); Phase 7 keeps only the deposit / steal exclusion.
- **Not done yet:** matching in-app transfers against the bank feed (it belongs with the transfer log in Phase 6).

### Phase 3 — Construction Accounts page, card and controls (10 h)
- [ ] Route `/liquidity/construction-accounts` (name `construction-accounts`) in `router/index.ts`. Add the entry to `shell/nav.ts` (sidebar, command palette) and keep `nav.test.ts` in step. Check the phone bottom nav at 390 px: if an eighth item doesn't fit, the page is in the sidebar and palette only, and is reached on a phone from the Liquidity page button (1 h)
- [ ] Direct links: a "Construction accounts" button in the Liquidity page header (theater mode), a link on each deal in the deal bar / `DealLegendPanel`, and a tile on the Dashboard (`LandingPage.vue`) with the total projected return and the count of deals needing a link or a top-up (1 h)
- [ ] `views/ConstructionAccounts.vue` + `components/liquidity/constructionAccount/ConstructionAccountCard.vue`, one card per deal (3 h):
  - deal name, property address, and LLC / Mercury workspace;
  - linked accounts: construction and primary checking (names and last 4 digits only), plus the previous accounts;
  - available balance; construction budget; loan draws pulled vs remaining to pull;
  - rehab cost (with "Edit rehab cost / budget", which opens the Bought deal edit); rehab payments made to date; unpaid rehab remaining;
  - each sum expands into bank / before-link / manual;
  - `projected_return_at_rehab_end` and `safe_to_steal_now`, plus the remaining deposit and any top-up needed; "amounts as of <time>";
  - actions: Link / Account settings / Switch account / Unlink; Deposit; Steal; Mark ready for close-out; Close out; Mark closed out; Reopen.

  An unlinked deal shows "Link a construction account".
- [ ] `ConstructionAccountSettingsModal.vue` (used for both link and edit) (1.5 h):
  - the account pickers (from the Mercury list `SettingsPanel` uses);
  - the two baselines, always editable;
  - the deposit target override, with the formula value shown beside it;
  - the keep-at-least buffer.
- [ ] `ConstructionAccountSwitchModal.vue`: the old account's totals, prefilled into the baselines, editable; "move $X to the new account first" while the old balance isn't $0 (0.75 h)
- [ ] `ConstructionAccountManualAdjustmentsList.vue`: add, edit and delete manual payments and draws (type, amount, date, note) (1 h)
- [ ] `ConstructionAccountTransactionsList.vue`: the bank transactions with their automatic and effective category; per row, an Ignore toggle, a category select and a note; "Restore automatic"; filters (all / draws / payments / own money / ignored) (1 h)
- [ ] Data-table fallback and phone layout per the design-system page rules (single column at < lg) (0.75 h)

### Phase 4 — Deposit and Steal modals (2.5 h)
- [ ] `ConstructionAccountTransferModal.vue`, shared by Deposit and Steal:
  - amount, the relevant balance, and what changes on the timeline;
  - Deposit is prefilled with `remaining_deposit` and capped at the checking's available balance;
  - Steal is prefilled with `safe_to_steal_now`. Above the keep-at-least buffer or the safe amount, it shows "you will need to top up $X later" and needs a confirm;
  - Close out is a Steal of the whole balance;
  - result: sent, or pending approval in Mercury.

  After a successful transfer it runs the refresh and reloads the liquidity store, so the deposit row is Done and the balances are current at once (2.5 h)

### Phase 5 — Timeline and preview additions (5.5 h)
- [ ] `TimelineChart.vue`: one fine horizontal line per active deal, in a thin lane band at the bottom of the plot (one lane per deal, so lines never overlap). Each line is drawn in the deal's colour (`components/liquidity/dealColors.ts`), with its name at the left end. It runs from contract signed to the refi (approved date, or planned; a late refi runs through today). Colours go through the existing chart-token rules, and the lines don't animate (2.5 h)
- [ ] `dealImpactGeometry.ts`: a new range `until_last_deal_ends` ("Until last deal ends"), alongside Deal lifecycle / 6 months / 1 year / All. It starts a week before today and ends on the latest refi date among the active imported deals and the incoming deal (1 h)
- [ ] Default range (`DealImpactChart.vue`, today hard-coded to `deal_lifecycle`): a prop set by the preview from the incoming deal's lowest-ARV cash-out (`cash_out_routi_conservative`, the "Cash-Out Routi (Lowest ARV)" result). If it's > 0, default to "Deal lifecycle"; if it's ≤ 0, default to "Until last deal ends" (1.5 h)
- [ ] `components/deal/brrr/RehabSection.vue`, under "Actual Rehab Cost": a visible hint, "Did you include flooring? Double-check the square footage and the labor." (0.5 h)

### Phase 6 — Transfer backend and its security (6 h)
- [ ] Separate write token per workspace, `MERCURY_TRANSFER_API_TOKEN_<LABEL>`, read only by the transfer function. The read path never sees it, and transfers never use the read tokens. Same `Secret` hygiene; the URL is pinned to the one transfer endpoint (1.5 h)
- [ ] Table `liquidity_construction_account_transfers`: deal; `transfer_direction` (`deposit_into_construction_account` / `steal_to_primary_checking`); amount; idempotency key (unique); Mercury transfer id; status; `requested_at`; `requested_by` (1 h)
- [ ] `POST /liquidity/construction-accounts/{bought_deal_id}/deposit` and `/steal` (body: `amount_dollars`, `idempotency_key`; Steal also takes `confirm_amount_exceeds_safe_to_steal`). Guards:
  - `require_recent_auth` (the passkey step-up; the axios interceptor retries with the same body, so the same key);
  - source and destination come only from the stored link, never from the request;
  - 0 < amount ≤ the source's available balance;
  - Steal above safe-to-steal gives a 409 (naming the coming top-up) unless confirmed;
  - no transfer on a closed-out link;
  - a per-hour rate limit (`CONSTRUCTION_ACCOUNT_TRANSFERS_PER_HOUR`, default 5);
  - an audit row with the deal, the direction and the Mercury transfer id;
  - a successful Deposit marks the deposit row Done when `remaining_deposit` reaches 0 (3.5 h)

### Phase 7 — MCP support (2 h)
- [ ] New GET endpoints (status, transactions, switch preview) become read-only tools automatically. Write tools on the app's own data are clearly described: link / settings, manual adjustments, transaction overrides, close-out marks, refresh. Unlink, delete-adjustment and switch are annotated destructive. `INSTRUCTIONS` gets the construction-account model, the formula and the manual controls in place of "stolen money" (1.5 h)
- [ ] **The deposit and steal endpoints are NOT MCP tools**: add both to `EXCLUDED_TOOL_NAMES` (`mcp_server.py`), so Claude never moves money. Claude can still read the projection and safe-to-steal, and log manual entries. `test_mcp_tools.py` and `test_mcp_annotations.py` pin it (0.5 h)

### Phase 8 — Security task (2 h)
- [ ] From `.claude/security.md`: *"Please check through all the code you just wrote and make sure it follows security best practices. make sure there are no sensitive information in the frontend and there are no vulnerabilities that can be exploited throughout all the code in this repo."* Specifically:
  - no token or full account number reaches the frontend or the logs;
  - the transfer token can't be reached from any read path;
  - the caller can't choose the source or destination;
  - idempotency holds under the reauth retry;
  - an override can't target another deal's transaction;
  - manual entries are validated (amount bounds, note length);
  - CSRF and session checks apply on every new write;
  - the Mercury error text is never relayed.

  Then update `SECURITY_PLAN.md` §3.3: write-capable transfer tokens (IP allow-listed, narrowest scope, rotation runbook) are now an asset. Run `/security-review` on the branch (2 h)

### Phase 9 — Finish (1 h)
- [ ] Goldens and regression snapshots in `Golden update:` commits; the README liquidity section, the routes table and the env-var table (`MERCURY_TRANSFER_API_TOKEN_<LABEL>`, `CONSTRUCTION_ACCOUNT_TRANSFERS_PER_HOUR`); check off this plan; push; open the PR (1 h)

## Tests

**Unit**
- `test_cash_needed_schedule.py`:
  - deposit / return amounts for a positive steal, a negative steal and a $0 budget;
  - the appliances row unchanged;
  - Σ rows = −(total cash needed − cushion);
  - cent rounding.
- `test_construction_account_projection.py`, one case each:
  - an advance draw, a reimbursement draw, a steal, a deposit and a change order;
  - linked mid-rehab with baselines (the $30k case), then the baselines edited later;
  - a manual payment from another account, and a manual draw wired to checking;
  - an ignored transaction (left out of the sums, still in the balance);
  - re-categorised as a refund, as own money (counts toward the deposit), and as a draw;
  - the deposit target override;
  - the keep-at-least buffer lowers safe-to-steal;
  - a top-up needed; a partial manual deposit;
  - an in-app transfer not yet in Mercury's list (counted once), then present (still once);
  - failed and cancelled transactions skipped;
  - the breakdown by source adds up to each sum.
- `test_mercury_client.py`: the read path calls only `/accounts` and the transactions URL with read tokens; the transfer path calls only the transfer URL with the transfer token; no token in logs or exceptions.
- Frontend (Vitest):
  - the card's states (unlinked, deposit due, top-up, ready for close-out, closed out, "amounts as of");
  - the settings modal: always editable, the formula value shown beside the override;
  - the switch modal is blocked while the old balance isn't $0;
  - the manual adjustments list (add / edit / delete);
  - the transactions list (ignore, re-categorise, restore, filters);
  - the transfer modal's validation and warnings;
  - `dealImpactGeometry` `until_last_deal_ends`, and the default range for cash-out > 0 vs ≤ 0;
  - lifespan lanes never overlap;
  - `nav.test.ts`;
  - the flooring hint.

**Integration**
- `test_liquidity_construction_account.py` (Mercury mocked):
  - link / settings / unlink validation; baselines editable after linking;
  - only deals between purchase and an approved refi are listed;
  - manual adjustment CRUD moves the return row;
  - a transaction override moves the return row, and is refused for another deal's transaction;
  - switch account: 409 while the old balance isn't $0, then the baselines are folded in and the deposit stays Done;
  - mark ready / mark closed out / reopen toggle the return row's Done;
  - a Mercury failure keeps the last row amounts;
  - refresh is idempotent; the linked account is excluded from counted-as-cash;
  - a change order through the deal edit → the re-sync shows the return row changing; the appliances row stays.
- Deposit and steal endpoints:
  - 403 without step-up;
  - the steal gives 409 above safe-to-steal without confirm;
  - source and destination always come from the link;
  - the same idempotency key → one transfer;
  - 429 after the rate limit;
  - refused on a closed-out link;
  - the audit row has no amount;
  - a deposit marks the deposit row Done.
- `test_migrations.py`: the new tables; the out-of-date flag set on imported BRRRR deals.
- `test_mcp_tools.py`: the new read and own-data tools are listed with their annotations; deposit and steal are absent.

**E2E (Playwright)**
- `flows/construction-accounts.spec.ts`:
  - open the page from the sidebar and from the Liquidity button;
  - link mid-rehab with baselines; Deposit → step-up → the deposit row is Done and the timeline refreshes;
  - a mocked draw arrives → the timeline balance is unchanged;
  - add a manual payment → the projection rises by it;
  - ignore a bank transaction → the projection updates;
  - edit a baseline;
  - Steal within the safe amount → checking rises and the return row falls by the same amount;
  - Steal above the safe amount → the warning, then confirm → a top-up row today;
  - switch account; mark ready; Close out; Reopen.
- `flows/liquidity.spec.ts` and `flows/liquidity-deal-import.spec.ts`:
  - lifespan lines are visible with the deal names;
  - the import preview defaults to "Until last deal ends" for a deal with a lowest-ARV cash-out ≤ 0, and to "Deal lifecycle" otherwise;
  - the new chip works.
- Existing checks stay green (`checks/shell`, `alignment`, `axe-modals`, `chart-tokens`, `no-live-tweens`, `theme`); their goldens are updated only in `Golden update:` commits.

## Verification
- `pytest BackEnd/tests` and `python BackEnd/verify_regression.py`; `npm run test` and the Playwright specs above in `frontend/`.
- Manually, against a mocked Mercury in dev, the $30k case:
  - link with "pulled before $30k / paid before $0"; Deposit the cushion in-app → the deposit row is Done;
  - move the $30k into the account → the timeline's net change is the cushion plus the spread;
  - log a $2k credit-card material run as a manual payment → the projection rises by $2k;
  - ignore a stray transaction → it leaves the sums;
  - Steal $5k → checking +$5k, return row −$5k.
- Open an import preview for a deal whose lowest-ARV cash-out is ≤ 0 → it opens on "Until last deal ends".
- MCP: list the tools; read a construction account's status and transactions; log a manual payment; confirm no deposit or steal tool exists.

Total estimate: about 46 h.
