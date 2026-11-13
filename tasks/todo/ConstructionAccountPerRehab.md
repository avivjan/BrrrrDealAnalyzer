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

## Remaining work, revised on 2026-11-13 (this replaces Phases 3–9 below)

Branch `ConstructionAccountPerRehab`, pushed. The full plan with its decisions and model is `tasks/todo/ConstructionAccountPerRehab.md`; this file covers what is left. Step A copies it into that file.

## Context

Phases 0–2 are built, tested and pushed: the schedule's deposit and return rows, the construction account tables, the projection, the Mercury transactions read, the 15 `/liquidity/construction-accounts/*` routes with their MCP tools, and the three live liquidity rows.

Four requirements reshape the rest:
1. **Every change that affects the timeline opens a confirmation prompt at once.** Nothing waits passively, and nothing changes the timeline silently.
2. **Every number tied to the construction account is on its page**, and every number you can decide is editable there.
3. **Nothing in a config file.** Every setting is in the UI and the database.
4. **Mercury as close to real time as it allows.**

## Decisions

**From your answers**
- **Mercury tokens stay in the hosting dashboard's secret settings** (read tokens as today, plus one transfer token per LLC). The UI shows which LLCs have which token and what is missing. Everything else is UI + database.
- **Polling and webhooks are both built now.** The webhook part ships untested against the real Mercury: I could confirm its format only from third-party guides.
- **Rehab cushion and deposit target are one figure, stored once.** The number is the Bought deal's `rehab_cushion`; the construction account has no deposit target of its own, so the two cards can never disagree. The `planned_deposit_override_dollars` column added in Phase 2 is removed (it was never deployed). When the rehab costs more than the construction budget, that extra is added automatically and shown beside the figure: "cushion $5,000 + rehab beyond the budget $10,000 = $15,000 to deposit". The suggested value is the app's default cushion ($5,000), with a one-click "Reset to suggested".

**Requirement 1 — always a prompt, at the point of the change**

One prompt everywhere: **"This changes the liquidity timeline"**, with the before → after list of rows (the existing `DealCashRowChangesList`), any row you edited by hand that the change disagrees with ("Use the new value" per row), and two buttons: **Confirm** and **Cancel**.

- **An edit on the Construction Accounts page** (rehab cost, budget, contingency, cushion, deposit target, a baseline, a manual payment or draw, ignoring or re-categorising a transaction, link, switch, unlink, close out, reopen):
  - the prompt opens before anything is saved, showing the figures before → after and the rows before → after;
  - Confirm saves the edit and updates the timeline together;
  - Cancel discards the edit. Nothing is saved.
- **Deposit and Steal:** their own modal is the prompt. It shows the rows before → after next to the amount; there is no second prompt.
- **A deal card save** (My Deals, Bought; cards autosave):
  - when the save changes the deal's liquidity rows, the prompt opens as soon as the save lands;
  - Confirm updates the timeline;
  - Cancel leaves the rows as they are. The prompt opens again on the next save of that deal and whenever Liquidity or Construction Accounts opens. There is no passive banner to find.
- **A change made outside the browser** (through the Claude connector, or the deploy that introduces these rows): the prompt opens the next time Liquidity or Construction Accounts opens, one deal at a time.
- **A change the bank reports** (a transfer you made in Mercury itself, found by a poll or a webhook) is not an edit, so there is nothing to cancel. It is applied at once, and a **"Timeline updated from the bank"** modal opens with the same before → after list and one button, **OK**. The daily move of a top-up row to today's date does not open it.
- **An edit that changes no timeline row** (the buffer to keep, a note, a setting) saves directly, with a short "Saved" notice.
- **Feedback never stacks.** After a Confirm, one "Liquidity timeline updated" notice shows; editing several figures in a row updates that same notice in place ("3 edits · 5 rows") instead of adding one per edit. If a change for a deal arrives while that deal's prompt is already open (a bank-reported change, or a second pending change), its rows and any new disagreements are merged into the open prompt; a second prompt never opens on top.
- The "rows wait for a Re-sync" banner and the `rows_wait_for_a_resync` field are removed. The existing "Liquidity out of date" badge on a deal card becomes a button that opens the same prompt.
- A legacy cushion row you had already marked Done becomes a deposit row that is already Done when you confirm, so no overdue deposit appears.

**Requirement 2 — every number, on one sheet per deal**

Editable in place (tap the figure, type, Enter → the prompt of Requirement 1):

| Group | Editable figures |
|---|---|
| Rehab | actual rehab cost; contingency %; construction budget (written to the Bought deal, validated like a deal save) |
| Your own money | **rehab cushion / deposit target** (one figure, written to the Bought deal; the suggested $5,000 and "Reset to suggested" beside it); buffer to keep in the account |
| Before this account | loan draws pulled before; rehab paid before |
| By hand | each manual payment and manual draw (amount, date, note) |
| Bank transactions | each transaction's category, ignored flag and note |
| Dates | rehab completed and refi dates, through the existing milestone modal; the return row's date |

Shown (derived or from the bank), each with a one-line "how this is computed":

| Group | Figures |
|---|---|
| Account now | current balance; available balance; pending money in and pending money out (not settled yet); the primary checking's available balance; amounts as of; next Mercury read |
| Rehab cost | actual + contingency = rehab cost; over or under the budget (the original spread) |
| Loan draws | pulled until now = bank feed + before this account + by hand; remaining to pull; % of the budget pulled; last draw (date, amount); number of draws |
| Rehab paid | paid until now = bank feed + before this account + by hand; unpaid remaining; % of the rehab paid; **paid per payee** (GC, electrician, …); last payment (date, amount) |
| Your own money | total to deposit = cushion + rehab beyond the budget; deposited so far; remaining deposit; stolen so far; your own money still in the account (deposited − stolen); lender's spread already taken vs still to take |
| Outcome | projected return at rehab end, split into "your own money back" and "spread"; safe to steal now, and which limit caps it (balance, buffer or projection); top-up needed |
| On the timeline | the deposit, return and top-up rows as the timeline has them: date, amount, Done or open, overdue |
| Not in this account | appliances (amount, date): its own timeline row, paid from checking |
| Bank feed health | transactions counted; ignored; re-categorised; failed or cancelled; last transaction date |
| Transfers made in the app | each Deposit and Steal: date, amount, status at Mercury; transfers left this hour; the per-transfer maximum |
| History | previous construction accounts and what each carried over |

Above the cards, **totals across every account**: balance, projected return, safe to steal, remaining deposits, top-ups needed, and how many accounts need attention (deposit due, top-up needed, Mercury unavailable).

**Requirement 3 — settings in the UI, stored in the database**
- New columns on `liquidity_settings`, edited in a "Construction account settings" drawer on the page through the existing `PUT /liquidity/settings`:
  - `construction_account_refresh_interval_seconds` (default 30, 15–600);
  - `construction_account_refresh_when_window_regains_focus` (default on);
  - `construction_account_in_app_transfers_enabled` (default on: a kill switch);
  - `construction_account_transfers_per_hour_limit` (default 5);
  - `construction_account_maximum_single_transfer_dollars` (default 100,000).
- These replace the two environment variables the earlier plan introduced. No new environment variable is added except the transfer tokens.
- A read-only "Mercury connection" block in the same drawer, per LLC. It never shows a token or a secret's value.
  - **Tokens:** read token present or missing; transfer token present or missing. For a missing one, the exact name the backend expects, ready to copy: `MERCURY_API_TOKEN_<LABEL>` and `MERCURY_TRANSFER_API_TOKEN_<LABEL>` with the LLC's label filled in. For an LLC with no token yet, a small box takes its label and shows both names.
  - **Instant updates:** on or off; "Last instant event: 2m ago" or "Waiting for the first event"; and the most recent registration or verification error with its time, if there was one.

**The same deal edited in two places**
- The four rehab figures live on the Bought deal, so the Bought deal card and the Construction Accounts card edit the same stored numbers.
- A confirmed edit on the Construction Accounts card bumps the deal's `updated_at` and reloads the deal in the frontend's Bought deal store, so the Bought board shows the new figures without a reload.
- A Bought deal form that was open somewhere else (another tab or device) cannot silently overwrite them: the Bought deal save sends the `updated_at` the form was loaded with, and the server refuses a stale save (409). The form then reloads the deal and says "This deal was changed elsewhere; your form was refreshed".
- Editing the cushion on the Bought deal card changes the same figure the Construction Accounts card shows, and opens the timeline prompt like any other deal save.

**Requirement 4 — live Mercury**
- **Polling.** While the Construction Accounts or Liquidity page is open and the tab is visible, the app re-reads Mercury every `construction_account_refresh_interval_seconds`, and at once when the window regains focus. These reads bypass the 60-second cache.
- **Burst after a transfer.** After a Deposit, Steal or Switch: read at once, then at 2, 5, 10, 20 and 40 seconds, stopping when the bank feed shows the transfer.
- **One live read covers the whole LLC.** A read of an LLC fetches all of its accounts (every balance, not only construction accounts) and the transactions of its linked construction accounts. So the main Liquidity cash balance is live too, whether or not any construction account is linked.
- **One gate per LLC, shared by every reader.** The general balance read (`GET /liquidity/mercury-balance`), the construction account refresh, and the webhook all go through one function. It keeps, per LLC in the database (so every server process shares it): the last accounts snapshot, when it was read, and when the next read is allowed.
  - At most one Mercury read per LLC every 10 seconds, however many tabs, pages or readers ask. A reader that asks sooner gets the stored snapshot, never a second call.
  - On a "slow down" answer (429) to any call, that LLC backs off for all readers, doubling up to 5 minutes (honouring `Retry-After`), and the pages say when the next read is.
  - Mercury's limits are not published, so these numbers are conservative guesses.
- **`last_changed_at` moves when either thing changes:** a linked construction account's numbers, or the LLC's overall cash balance (the accounts counted as cash).
- **Webhooks.** A "Turn on instant updates" button per LLC registers our address with Mercury. A webhook is registered per LLC, so every valid event means "something moved in this LLC". On each one the server discards that LLC's cached balances, reads the LLC fresh at once, stores the new balances, refreshes its linked construction accounts and writes their rows. The event's contents are never trusted or stored: it only says "look now". With instant updates on, the open page checks our own database every 5 seconds (no Mercury call) and reloads what changed; polling continues as a safety net.
- **Both pages show it without a reload.** When a poll or the 5-second check finds a change, the browser reloads the construction account cards and the main Liquidity cash balance (the header figure and the timeline's starting balance). A cash balance change is the bank's fact, not a row change, so it opens no prompt.
- Poll reads are audited only when they change something or fail, so the audit log is not flooded. Manual refreshes and every write are still audited.

**Carried over from the previous revision**
- The page is in the sidebar and command palette, not the phone's seven-tab bottom bar; on a phone it is reached from the Liquidity button and the Dashboard tile.
- The Dashboard tile is a plain link (the Dashboard makes no request of its own).
- The import preview gets `cash_out_wire_at_lowest_arv_dollars` from the backend for its default range.
- Browser tests get a fake Mercury inside the test server only.
- The transfer backend is built before the Deposit / Steal modal.

## Todo

### Step A — Plan file (15 min)
- [x] Copy this revision into `tasks/todo/ConstructionAccountPerRehab.md`; commit.

### Step B — Backend for the four requirements (15.5 h)
- [x] **Preview before every construction account write** (2.5 h): each write route takes `preview_only` (query, default false). With it, the route does the whole change inside the database transaction, builds its answer, and rolls back. The business functions stop committing; the router commits or rolls back. Every answer carries `status_before`, `status_after` and `liquidity_row_changes` (the `DealCashRowChangesRes` shape, with the hand-edited rows that disagree and `use_the_new_value_for`).
- [x] **A confirmed write syncs the whole deal** (1 h): `write_construction_account_rows_of_deal` no longer skips a flagged deal on a confirmed write; it runs the full sync and clears the flag. A background refresh still leaves a flagged deal's rows to its prompt. `rows_wait_for_a_resync` is removed.
- [x] **Deal saves keep flagging; the prompt is the frontend's** (0.5 h): the save path is unchanged (`mark_liquidity_rows_out_of_date_if_the_save_changed_them`); the existing `import-preview` / `import` routes are the prompt's preview and confirm. New: a Done legacy `rehab_cushion` row makes the new deposit row Done at confirm.
- [x] **Rehab figures route** (1.5 h): `PUT /liquidity/construction-accounts/{bought_deal_id}/rehab-figures` (any of `actual_rehab_cost_dollars`, `rehab_contingency_percent`, `construction_budget_dollars`, `rehab_cushion_dollars`; `preview_only`). Validated with `validate_brrr_inputs_for_saved_deal` on `deal_as_attributes(deal, **changes)` (the pattern of `apply_milestone_change`), written to the Bought deal with its `updated_at` set to now, then the full sync. Works for an unlinked deal too. The answer carries the deal's new `updated_at`.
- [x] **One cushion figure** (1 h): remove `planned_deposit_override_dollars` from the model, the link request, the status and the projection inputs (`planned_deposit = rehab_cushion + max(0, −original_steal)`, always); the status answers `rehab_cushion_dollars`, `rehab_beyond_the_construction_budget_dollars`, `total_to_deposit_dollars` and `suggested_rehab_cushion_dollars` (the default of `BrrrLifecycleColumns.rehab_cushion`). Tests of Phase 2 updated.
- [x] **Stale Bought deal saves** (1.5 h): `BoughtBrrrDealCreate` gains the optional `updated_at_the_form_was_loaded_with`; `update_bought_deal` answers 409 when it is older than the stored `updated_at` (compared to the microsecond the response gave). Without the field (the Claude connector, older clients) a save behaves as today.
- [x] **The extra numbers** (2.5 h):
  - stored on the link at each refresh, next to the bank sums: pending money in / out, the checking's available balance, the counts (counted, ignored, re-categorised, failed), the last draw and last payment, the number of draws, and rehab paid per payee (JSON);
  - computed in the status: the percentages, deposited / stolen / own money still inside, the return's split, which limit caps safe-to-steal, the three timeline rows, the appliances row, the rehab-completed and refi dates with their approval;
  - `GET /liquidity/construction-accounts` also answers the totals across accounts.
- [x] **Bank-reported changes** (0.5 h): the refresh answers, per deal, the row changes it just applied, for the "Timeline updated from the bank" modal (a top-up row's date-only move is left out).
- [x] **Settings** (1 h): the five columns (model, migration step, `LiquiditySettingsUpdate` / `Res` with bounds); `GET /liquidity/mercury-connection-status`, per LLC label (every label with a token, a link or a webhook): `has_read_token`, `has_transfer_token`, `read_token_environment_variable_name`, `transfer_token_environment_variable_name`, `instant_updates_are_on`, `last_valid_event_received_at`, `last_webhook_error_message`, `last_webhook_error_at`. Names and times only, never a value.
- [x] **One shared, paced Mercury reader** (3.5 h): `BL/liquidity/common/mercury_reads.py`, the only caller of `mercury_client` from now on.
  - Table `liquidity_mercury_workspace_reads`, one row per LLC label: `accounts_snapshot` (JSON: the summarised accounts, as `mercury_client` already returns them, with no token and only the last four digits of a number), `counted_as_cash_balance_dollars`, `last_mercury_read_at`, `next_mercury_read_not_before`, `consecutive_slow_down_answers`, `last_changed_at`.
  - `mercury_client` gains a per-LLC accounts read and `use_cache=False` on both reads; a 429 raises a `MercurySlowDownError` carrying `Retry-After`.
  - `read_workspace(db, label, linked_construction_account_ids, want_fresh)`: inside the floor or the back-off it answers the stored snapshot; otherwise it reads the accounts once and each linked account's transactions, stores the snapshot, and moves `last_changed_at` when the counted-as-cash balance or a linked account's sums changed. A row lock makes two processes asking together do one read.
  - `get_mercury_balance` (the general endpoint) and `refresh_construction_accounts` both use it, so neither ever makes a call the other just made. `GET /liquidity/mercury-balance` takes `fresh` (default false: the snapshot if it is younger than the cache time, as today).
  - The refresh reads every LLC with a token, not only LLCs with a linked account. It answers `next_mercury_read_not_before`, `last_changed_at`, `cash_balance_changed` and `construction_accounts_changed`.
  - `GET /liquidity/construction-accounts/last-change` (database only): `last_changed_at`, `cash_balance_last_changed_at`, `construction_accounts_last_changed_at`.
  - Poll refreshes send `is_a_background_poll: true` and are audited only on change or failure.
- [x] MCP: descriptions and annotations for the new and changed routes; `INSTRUCTIONS` says to show the owner a `preview_only` answer before confirming a write.


**How Step B was built (2026-11-13), where it differs from the list above:**
- **The stale-save check is a query parameter**, `PUT /bought-deals/{id}?updated_at_the_form_was_loaded_with=…`, not a body field, so the Bought deal's request and response schemas stay as they were.
- **The twelve write tools' MCP answers point to the full status schema** (carried once by `list_liquidity_construction_accounts`) instead of repeating it: repeated, `tools/list` grew to 702 kB; now 545 kB.
- **A failed Mercury read never answers with the old snapshot**; a "slow down" answer does (it is pacing, not a failure).
- **Mercury reads inside a preview are rolled back with it**, pace included: a preview may cause one extra read later, never a write.
- **Not done yet:** `cash_out_wire_at_lowest_arv_dollars` on the import preview (it belongs with Step G).

### Step C0 — Navigation and shortcuts across the app (added on request, 7 h)

Today only My Deals opens a deal from a link (`/my-deals?openDeal=…`); the Liquidity legend's deal link goes to the board, not the deal; inspections name their linked deal without linking to it. The rule from now on: **wherever a deal, a row or an account is shown, one click reaches the same thing everywhere else.**

**One place builds every link** — `src/navigation/appLinks.ts`, pure functions returning router locations, used by every page (so a link can't drift from what the page reads):

| Link | Opens |
|---|---|
| `dealOnItsBoard(board, id, type)` | `/my-deals?openDeal=…` (exists) or `/bought-deals?openDeal=…&dealType=…` (new): the deal's modal |
| `dealOnTheLiquidityTimeline(board, id)` | `/liquidity?deal=<board>:<id>`: the legend opens on that deal, expanded and highlighted on the chart |
| `transactionOnTheLiquidityTimeline(id, date)` | `/liquidity?transaction=<id>&day=<date>`: the chart centres on that day and its day view opens with the row highlighted |
| `constructionAccountOfDeal(id, section?)` | `/liquidity/construction-accounts?deal=<id>&open=<section>`: scrolls to that card, highlights it, and opens a section (`transactions`, `manual-entries`, `settings`, `link`) |
| `inspection(id)` | the inspection's summary (exists) |

Each page reads its query once, acts, then clears it with `router.replace` (as `MyDeals.vue` does), so a refresh doesn't reopen it and Back returns to where you came from. An unknown id shows "That deal is no longer here" instead of failing silently.

**The shortcuts, by place**

| Where you are | What you can jump to |
|---|---|
| **Bought deal card and modal** | "On the timeline" (when imported); "Construction account" with its state as a chip (not linked / deposit due / top-up needed / live); its inspections |
| **My Deals card and modal** | "On the timeline" (when imported); "Open its Bought copy" (opens the copy's modal, replacing today's link to the board) |
| **Liquidity legend, per deal** | "Open deal" (the modal, not the board); "Construction account"; each overdue row → its day |
| **Liquidity day view, per row** | "Open deal" for a deal's row; "Construction account" for a deposit, return or top-up row |
| **Liquidity top bar** | "Construction accounts" (and in the phone's ⋯ menu) |
| **Import preview** | after Import: "See it on the timeline" |
| **Construction account card** | "Open deal"; "Show on the timeline"; each row of "On the timeline" → that row on the timeline; each "needs attention" chip → the action that fixes it (Deposit, the top-up row); "Open Mercury" (app.mercury.com, a new tab: for transfers you make there) |
| **Inspections list and summary** | the linked deal → its modal |
| **Dashboard** | "Construction accounts" tile |

**Keyboard and command palette**
- **Go-to keys** anywhere outside a text field: `g` then `d` Dashboard, `a` Analyze, `m` My Deals, `b` Bought, `l` Liquidity, `c` Construction accounts, `r` REPS, `i` Inspections. Listed in the palette as hints and in a `?` help sheet.
- **Find any deal from ⌘K:** each deal gets "Open <address>", and when it applies "<address> on the timeline" and "<address> construction account". The list comes from the existing compact cross-board `GET /deals`, read once when the palette first opens (the palette's one network call; its golden is updated in a `Golden update:` commit).
- Palette commands for "Construction account settings" and "Liquidity settings" (navigation with `open=settings`).

**Files:** `src/navigation/appLinks.ts` (+ test), `src/composables/useDeepLinkQuery.ts` (read once, act, clear), `src/composables/useGoToKeyboardShortcuts.ts` (in `AppShell.vue`), `shell/commands.ts` and `CommandPalette.vue`, `views/BoughtDeals.vue`, `views/MyDeals.vue`, `components/BoughtDealCard.vue`, `components/DealCard.vue`, `liquidity/ImportDealToLiquidityButton.vue`, `liquidity/theater/LiquidityTheaterMode.vue`, `theater/DealLegendPanel.vue`, `theater/DayTransactionsModal.vue`, `liquidity/dealImpact/DealImpactView.vue`, `views/InspectionsHome.vue`, `views/InspectionSummary.vue`, and the new page.

**Tests:** Vitest for `appLinks` (every link and what each page reads back), the deep-link composable (acts once, clears the query, unknown id), the go-to keys (ignored while typing), and the palette's deal commands. Playwright `e2e/flows/navigation-shortcuts.spec.ts`: Bought deal → timeline (legend open on it) → Construction account (card highlighted) → Open deal (modal) → Back returns each step; a day-view row → its deal; `g` `c` opens the page; ⌘K "construction" + an address opens that card; a deep link to a deleted deal shows the notice.

- [x] **Built** (`f1878de` and the C0 commit): `appLinks.ts`, `useDeepLinkQuery.ts`, go-to keys with the `?` sheet (`KeyboardShortcutsHelp.vue`), ⌘K deal and settings commands, deep links on Bought, Liquidity (deal, row and day, settings) and Construction Accounts, links on the legend, the day view, the overdue strip, the import button, the Bought card, the inspections list, the Dashboard tile, and the notice's "View on the timeline" going to the deal's rows after an import or a construction account edit. Vitest and `navigation-shortcuts.spec.ts` (desktop and phone Chromium) pass.
- [x] The Bought card's construction account state chip (built in Step D). Not done on purpose: a deal link on the inspection summary, which is a public share page.

### Step C — Construction Accounts page (15 h)
- [x] **Types, API, store** (2 h): `src/types/constructionAccount.ts`, `src/api/constructionAccount.ts`, `src/stores/constructionAccountStore.ts`. Every edit goes through one store function: preview → prompt → confirm (or cancel), then it replaces the deal's status, reloads the liquidity rows, and after a rehab-figures edit reloads that deal in `boughtDealStore`.
- [x] **The prompt and the notice** (2 h):
  - `components/liquidity/LiquidityTimelineChangePrompt.vue`: figures before → after, rows before → after through `DealCashRowChangesList.vue`, Confirm / Cancel; an OK-only mode for bank-reported changes.
  - One prompt per deal: a queue opens pending prompts one at a time, and a change for the deal whose prompt is open is merged into it (the preview is re-read; new disagreements are added to the list).
  - `components/liquidity/LiquidityRowsChangedNotice.vue`: the single "Liquidity timeline updated" notice, updated in place with a running count of edits and rows while it is visible.
- [x] **Route and navigation** (1 h): route `/liquidity/construction-accounts`; `shell/nav.ts` item with `shownInThePhoneBottomBar: false`, filtered in `AppMobileNav.vue`; a button in the Liquidity top bar and its phone ⋯ menu (`theater/LiquidityTheaterMode.vue`); a link per Bought deal in `theater/DealLegendPanel.vue`; a plain Dashboard tile (`LandingPage.vue`).
- [x] **Page, totals and card** (4.5 h): `views/ConstructionAccounts.vue`, `ConstructionAccountTotals.vue`, `ConstructionAccountCard.vue` with one small component per group of the Requirement 2 tables, and `ConstructionAccountEditableFigure.vue` (tap to edit, Enter saves, Escape cancels; modelled on `liquidity/InlineAmountEditor.vue`).
  - Header: "Refresh from Mercury", "amounts as of <time>", the next-read time while backing off, a banner while Mercury is unavailable.
  - Each card opens on the outcome and the account-now figures; the other groups expand.
  - Actions: Link, Switch account, Unlink, Mark ready for close-out, Mark closed out, Reopen; Deposit, Steal and Close out arrive in Step E.
- [x] **Link and switch modals** (2 h): `ConstructionAccountSettingsModal.vue` (first link: the two account pickers from `liquidityApi.getMercuryBalance()`, checking limited to accounts counted as cash in the same LLC, plus the baselines; no deposit target field: it is the cushion on the card) and `ConstructionAccountSwitchModal.vue`.
- [x] **Lists** (2 h): `ConstructionAccountManualAdjustmentsList.vue`, `ConstructionAccountTransactionsList.vue` (ignore, category, note, restore, filters) and the paid-per-payee table.
- [x] **Settings drawer** (1.5 h): `ConstructionAccountSettingsDrawer.vue` with the five settings and the Mercury connection block (token status with the expected names to copy, the label box for a new LLC, instant updates on / off, the last event time, the last error).

- [x] Vitest for the two stores, the prompt and notice, the card, the modals, the lists and the drawer (moved here from each item above, 2 h) Done for the two stores (`liquidityTimelineChangePromptStore.test.ts`, `constructionAccountStore.test.ts`: the prompt, the queue, merging, OK-only, the notice) and the transfer modal; the card, the link and switch modals, the lists and the drawer are covered end to end in `construction-accounts.spec.ts`.

### Step D — Prompts on deal cards, and live refresh (6 h)
- [x] **Deal cards** (1.5 h): in `MyDeals.vue` and `BoughtDeals.vue`, after an imported deal's save lands with its rows changed, the prompt opens (preview from `import-preview`, Confirm calls `import`). The "Liquidity out of date" badge (`ImportDealToLiquidityButton.vue`, `DealLegendPanel.vue`) opens the same prompt.
- [x] **Stale Bought forms** (1 h): the Bought deal save sends `updated_at_the_form_was_loaded_with`; on 409 the form reloads the deal from the server, keeps nothing of the stale edit, and shows "This deal was changed elsewhere; your form was refreshed". `boughtDealStore` gains a "reload one deal" action, also used after a confirmed rehab-figures edit.
- [x] **On opening Liquidity or Construction Accounts** (0.5 h): every deal still out of date is queued for its prompt.
- [x] **Live refresh** (3 h): `src/composables/useLiveMercuryRefresh.ts` (it covers more than construction accounts, so it is not named after them), used by both pages.
  - The interval poll, the focus / visibility refresh (not more than once per 5 seconds), pausing while the tab is hidden, the post-transfer burst, the 5-second database check while instant updates are on, and respect for `next_mercury_read_not_before`.
  - On `construction_accounts_changed`: reload the cards and the liquidity rows, and open the "Timeline updated from the bank" modal when rows changed.
  - On `cash_balance_changed`: `liquidityStore` gets `applyMercuryBalance()`, split out of `syncFromMercury`, which reads `GET /liquidity/mercury-balance` (served from the snapshot the poll or the webhook just stored, so no second Mercury call), updates the header's balance and popover, and re-anchors the timeline's starting balance to today. No prompt.
  - `liquidityStore.fetchAll` calls the refresh after `refreshLateRefis`; the page's own Mercury sync on load goes through the same shared reader.

- [x] The "Timeline updated from the bank" modal for a change a webhook applied (done in Step F).
- Step D tests: Vitest `useLiveMercuryRefresh.test.ts`, `useDealLiquidityRows.test.ts`; Playwright `deal-save-timeline-prompt.spec.ts`. New requests on the Bought board (accounts list) and Liquidity (refresh, connection status) change the `bought-deals-load` and `liquidity-load` goldens: refreshed in Step H with the Step B schedule goldens.

### Step E — Transfers (8.5 h)
- [x] **Backend** (6 h), as in the full plan, with these changes: the hourly limit, the per-transfer maximum and the kill switch come from the settings; `preview_only` answers the rows before → after for the modal; in-app transfers are matched to the bank feed so each counts once; the code tolerates a missing id or an unknown status in Mercury's answer and never retries on its own; deposit and steal are excluded from MCP.
- [x] **Modal** (2.5 h): `ConstructionAccountTransferModal.vue` for Deposit, Steal and Close out, showing the rows before → after; one idempotency key per open modal; starts the burst refresh on success.

- Step E notes: deposit and steal need a web session with a passkey used in the last minutes (`require_recent_auth`), whatever `AUTH_MODE` says, like the Member Loan. Transfer rows are kept after an unlink or a deal's deletion (the record of real money moved). Close out = a Steal of the whole available balance, then `mark-closed-out`. Tests: pytest `test_liquidity_construction_account_transfers.py`, `test_mercury_transfers.py`, the matching cases in `test_construction_account_projection.py`; Vitest `constructionAccountTransferRules.test.ts`, `ConstructionAccountTransferModal.test.ts`.

### Step F — Webhooks (5 h)
- [x] Table `liquidity_mercury_webhooks`: `mercury_workspace_label` (unique), `mercury_webhook_endpoint_id`, `signing_secret`, `receiving_path_token`, `turned_on_at`, `last_valid_event_received_at`, `last_webhook_error_message`, `last_webhook_error_at`. The secret is never returned by any route and is redacted from logs.
- [x] Errors recorded for the drawer, in our own words (never Mercury's raw text): a registration Mercury refused, and a received event that failed its signature or timestamp check. A valid event clears nothing: the drawer shows both the last valid event and the last error with their times.
- [x] `POST /liquidity/mercury-webhooks/{workspace_label}/turn-on` and `/turn-off` (passkey step-up): register or delete the endpoint at Mercury. The address is this app's public address taken from the request (https only) plus `/webhooks/mercury/{receiving_path_token}`.
- [x] `POST /webhooks/mercury/{receiving_path_token}`: public, self-protected. It checks the `Mercury-Signature` header (HMAC-SHA256 over the timestamp and the raw body, constant-time compare), refuses a timestamp older than 5 minutes, and limits the body size and the rate. Excluded from MCP.
- [x] On a valid event, for that LLC: discard the stored accounts snapshot and the in-memory summary cache, read the LLC fresh through the shared reader (`want_fresh`, bypassing the cache but still inside the 10-second floor and any back-off: a burst of events makes one read, and an event inside the floor schedules one read at the floor's end), store every account's balance and the counted-as-cash total, refresh the linked construction accounts and write their rows, and move `last_changed_at` if the cash balance or a linked account changed.
- [x] **Unverified, said on screen if it fails:** which token Mercury accepts for registering (the transfer token is tried first, then the read token), and the exact event names.
- Step F notes: the receiver is `routers/mercury_webhooks.py` (public, not in the OpenAPI schema, never MCP). A webhook or a transfer asks for a fresh read without blanking the stored snapshot (`ask_for_a_fresh_read_of_workspace`). What an event changed on the timeline is kept on the workspace row and answered by `last-change`, so the 5-second check opens "Timeline updated from the bank" (the Step D leftover, done). Tests: pytest `test_mercury_instant_updates.py`; Vitest in `useLiveMercuryRefresh.test.ts`.

### Step G — Timeline and preview (6 h)
- [x] Deal lifespans (2.5 h), the "Until last deal ends" range and its default (2 h), the backend field for it (1 h), the flooring hint (0.5 h) — as in the previous revision.
- Step G notes: `utils/dealLifespans.ts` (one lane per deal in progress, contract to refi, a late refi dashed through today) drawn by `TimelineChart.vue` above the deal dots, still; `dealImpactGeometry.ts` gains `until_last_deal_ends`, `lastDealEndDate` and `defaultDealImpactRange`, fed by the backend's `cash_out_wire_at_lowest_arv_dollars` on the import preview; the flooring hint under "Actual Rehab Cost" (`form.hint.rehabCost.flooring`).

### Step H — Browser tests (5 h)
- [x] `frontend/e2e/backend/fake_mercury.py`, installed by `serve_throwaway.py`, off by default, driven through test-only routes (set any account's balance, add a transaction, count the calls made to it); it also plays the transfer call and can send a signed webhook. The call counter lets a test prove a webhook made exactly one read.
- [x] `e2e/flows/construction-accounts.spec.ts`:
  - open the page from the sidebar and the Liquidity button; link mid-rehab (prompt → Confirm);
  - edit rehab cost in place → the prompt shows the figure and the return row before → after; Cancel leaves both unchanged; Confirm changes both;
  - edit the cushion on the card → the Bought deal's cushion is the same number, and "Reset to suggested" returns it to $5,000; with a rehab above the budget the card shows "cushion + rehab beyond the budget = total to deposit";
  - edit three figures in a row → one notice, updated in place, never three;
  - a bank-reported change arrives while the deal's prompt is open → it is merged into that prompt;
  - with a Bought deal form open in a second tab, edit rehab cost on the card, then save the stale form → it is refused, reloaded, and the card's figure survives;
  - the drawer shows the expected token names for an LLC without a transfer token, "Waiting for the first event" before a webhook, the time of the last event after one, and the error after a wrongly signed one;
  - edit the buffer to keep → saved with no prompt;
  - an edit that disagrees with a hand-edited row → the prompt lists it with "Use the new value";
  - every group of the Requirement 2 tables shows its figures, and the totals add up;
  - Deposit → step-up → the deposit row is Done;
  - a fake draw arrives → it shows within one poll, with no modal (no row changed);
  - a steal made at the fake bank → the "Timeline updated from the bank" modal opens;
  - a signed webhook → the change shows without waiting for the poll;
  - **a signed webhook after money lands in a checking account that is not a construction account → the main Liquidity cash balance in the header changes, and the timeline's starting balance with it, with no page reload and no prompt** (in `liquidity.spec.ts`, with the poll interval set long so only the webhook can explain it);
  - with instant updates off, the same checking change shows on Liquidity within one poll;
  - manual payment, ignore a transaction, Steal within and above the safe amount, switch, close out, reopen;
  - change the refresh interval in the drawer → it is kept after a reload.
- [x] Deal cards: saving an imported deal opens the prompt; Cancel, then opening Liquidity, opens it again; Confirm updates the timeline. Lifespan lines; the preview default range; the flooring hint; the Dashboard tile.
- [x] Goldens (`e2e/golden/*`, `scripts/audit/golden/*`, the axe baseline) only in `Golden update:` commits.
- Step H notes: built `e2e/backend/fake_mercury.py` and `e2e/flows/construction-accounts.spec.ts` (7 cases, desktop and phone, stable over repeated runs), plus `navigation-shortcuts.spec.ts` (C0) and `deal-save-timeline-prompt.spec.ts` (D). Cases the plan listed that are covered at another layer instead of the browser: the stale Bought form (Playwright through the API in `deal-save-timeline-prompt.spec.ts`), "Use the new value", manual entries, ignoring a transaction, Steal within / above the safe amount, switch, close out and reopen (pytest and Vitest), the drawer's missing-token names (pytest, Vitest). Contract goldens re-recorded in `0b1be0d`. The source audit (`npm run audit`, `scripts/audit/golden`) already fails on `main` (2,195 lines of unrelated drift since its baseline); it is not re-baselined here.

### Step I — Security, docs, PR (3.5 h)
- [x] The security task from `.claude/security.md`, with the full plan's checklist plus: `preview_only` never leaves a write behind; the webhook route (signature, replay window, no trust in the payload, rate limit); the rehab-figures route (validated like a deal save); the settings bounds; no token or signing secret reaches the frontend or the logs. `SECURITY_PLAN.md` §3.3 updated. `/security-review` on the branch.
- [x] README, plan checked off, push, open the PR.
- Step I notes: fixes from the review: the webhook receiver rate-limits per sending IP (random addresses can no longer reset it), and two requests racing with one transfer key give a clean 409. `SECURITY_PLAN.md` §3.3.1 covers the transfer tokens and the webhook secret. `/security-review` on the branch: no vulnerability above the reporting bar (checked: no unauthenticated or MCP path to a transfer or to instant updates, accounts only from the link, the HMAC check, no token or secret in a response or a log, no string-built SQL, a CSPRNG receiving token). Residual: Mercury's transfer answer and webhook format are unverified against the real API.

## Tests by layer
- **Unit (pytest):** `preview_only` answers the same changes a confirmed write then makes, and leaves no row, link, adjustment or override behind; the Done carry-over of a legacy cushion; rehab-figures validation and the `updated_at` bump; the total to deposit with and without a rehab beyond the budget; a stale Bought deal save refused, a save without the field accepted; the connection status (expected names per label, last event, last error, never a value); each extra number (pending sums, per-payee totals, percentages, the return's split, the cap on safe-to-steal, totals); bank-reported changes without the top-up date move; settings bounds; webhook signature (valid, wrong secret, old timestamp, altered body); transfer guards and matching.
- **Unit (pytest), the shared reader:** a general balance read and a construction refresh inside 10 seconds make one Mercury accounts call between them; a 429 on either puts the LLC in back-off for both, doubling and honouring `Retry-After`; `last_changed_at` moves on a cash balance change with no construction account linked, on a linked account's change, and not when nothing changed; an LLC with no linked account is still read.
- **Unit (Vitest):** the prompt (Confirm, Cancel, OK-only, "Use the new value", the queue, merging into the open prompt); the notice updating in place; the stale-save handling of the Bought form; the drawer's connection block; the editable figure; each group of the card and the totals; each modal, list and the drawer; the live-refresh composable with fake timers (interval, focus, hidden tab, burst, back-off, the bank modal, and a cash balance change updating the store's balance and starting balance with no prompt); nav; lane layout; the preview range and default.
- **Integration (pytest):** every new and changed route in both modes; a deal save flags, `import-preview` lists and `import` applies; the webhook route end to end against the fake: **a signed event discards the LLC's cached `summarize_balance` data and the stored snapshot, makes one fresh accounts read, and `GET /liquidity/mercury-balance` then answers the new balance of a non-construction checking account without another Mercury call; the linked construction account and its rows are refreshed in the same event; `last-change` moves; a second event inside the floor makes no second call; an unsigned or wrongly signed event changes nothing and is recorded as the last error**; deposit / steal with step-up, idempotency, limits from the settings and the kill switch; MCP tool list and annotations.
- **E2E (Playwright):** Step H.

## Verification
- `pytest` and `python verify_regression.py verify` in `BackEnd/`; `npm run test`, `npm run build` and `npm run audit` in `frontend/`; the Playwright specs of Step H.
- In the running app against the fake Mercury: edit rehab cost on the card, read the prompt, cancel, edit again, confirm, and watch the timeline change without a reload; add a fake transaction and watch it appear within the interval, then at once with instant updates on.
- **Only you can verify against the real Mercury:** the first transfer (make it a small one), and turning on instant updates.

Remaining estimate: about 49 h (Steps A and B are done; Step C0 adds 7 h).

---

## The first version of Phases 3–9 (superseded by the revision above; kept for the record)

> Phases 3 to 9 were delivered through Steps C to I of the revised plan above (same scope, with the four requirements).

### Phase 3 — Construction Accounts page, card and controls (10 h)
- [x] Route `/liquidity/construction-accounts` (name `construction-accounts`) in `router/index.ts`. Add the entry to `shell/nav.ts` (sidebar, command palette) and keep `nav.test.ts` in step. Check the phone bottom nav at 390 px: if an eighth item doesn't fit, the page is in the sidebar and palette only, and is reached on a phone from the Liquidity page button (1 h)
- [x] Direct links: a "Construction accounts" button in the Liquidity page header (theater mode), a link on each deal in the deal bar / `DealLegendPanel`, and a tile on the Dashboard (`LandingPage.vue`) with the total projected return and the count of deals needing a link or a top-up (1 h)
- [x] `views/ConstructionAccounts.vue` + `components/liquidity/constructionAccount/ConstructionAccountCard.vue`, one card per deal (3 h):
  - deal name, property address, and LLC / Mercury workspace;
  - linked accounts: construction and primary checking (names and last 4 digits only), plus the previous accounts;
  - available balance; construction budget; loan draws pulled vs remaining to pull;
  - rehab cost (with "Edit rehab cost / budget", which opens the Bought deal edit); rehab payments made to date; unpaid rehab remaining;
  - each sum expands into bank / before-link / manual;
  - `projected_return_at_rehab_end` and `safe_to_steal_now`, plus the remaining deposit and any top-up needed; "amounts as of <time>";
  - actions: Link / Account settings / Switch account / Unlink; Deposit; Steal; Mark ready for close-out; Close out; Mark closed out; Reopen.

  An unlinked deal shows "Link a construction account".
- [x] `ConstructionAccountSettingsModal.vue` (used for both link and edit) (1.5 h):
  - the account pickers (from the Mercury list `SettingsPanel` uses);
  - the two baselines, always editable;
  - the deposit target override, with the formula value shown beside it;
  - the keep-at-least buffer.
- [x] `ConstructionAccountSwitchModal.vue`: the old account's totals, prefilled into the baselines, editable; "move $X to the new account first" while the old balance isn't $0 (0.75 h)
- [x] `ConstructionAccountManualAdjustmentsList.vue`: add, edit and delete manual payments and draws (type, amount, date, note) (1 h)
- [x] `ConstructionAccountTransactionsList.vue`: the bank transactions with their automatic and effective category; per row, an Ignore toggle, a category select and a note; "Restore automatic"; filters (all / draws / payments / own money / ignored) (1 h)
- [x] Data-table fallback and phone layout per the design-system page rules (single column at < lg) (0.75 h)

### Phase 4 — Deposit and Steal modals (2.5 h)
- [x] `ConstructionAccountTransferModal.vue`, shared by Deposit and Steal:
  - amount, the relevant balance, and what changes on the timeline;
  - Deposit is prefilled with `remaining_deposit` and capped at the checking's available balance;
  - Steal is prefilled with `safe_to_steal_now`. Above the keep-at-least buffer or the safe amount, it shows "you will need to top up $X later" and needs a confirm;
  - Close out is a Steal of the whole balance;
  - result: sent, or pending approval in Mercury.

  After a successful transfer it runs the refresh and reloads the liquidity store, so the deposit row is Done and the balances are current at once (2.5 h)

### Phase 5 — Timeline and preview additions (5.5 h)
- [x] `TimelineChart.vue`: one fine horizontal line per active deal, in a thin lane band at the bottom of the plot (one lane per deal, so lines never overlap). Each line is drawn in the deal's colour (`components/liquidity/dealColors.ts`), with its name at the left end. It runs from contract signed to the refi (approved date, or planned; a late refi runs through today). Colours go through the existing chart-token rules, and the lines don't animate (2.5 h)
- [x] `dealImpactGeometry.ts`: a new range `until_last_deal_ends` ("Until last deal ends"), alongside Deal lifecycle / 6 months / 1 year / All. It starts a week before today and ends on the latest refi date among the active imported deals and the incoming deal (1 h)
- [x] Default range (`DealImpactChart.vue`, today hard-coded to `deal_lifecycle`): a prop set by the preview from the incoming deal's lowest-ARV cash-out (`cash_out_routi_conservative`, the "Cash-Out Routi (Lowest ARV)" result). If it's > 0, default to "Deal lifecycle"; if it's ≤ 0, default to "Until last deal ends" (1.5 h)
- [x] `components/deal/brrr/RehabSection.vue`, under "Actual Rehab Cost": a visible hint, "Did you include flooring? Double-check the square footage and the labor." (0.5 h)

### Phase 6 — Transfer backend and its security (6 h)
- [x] Separate write token per workspace, `MERCURY_TRANSFER_API_TOKEN_<LABEL>`, read only by the transfer function. The read path never sees it, and transfers never use the read tokens. Same `Secret` hygiene; the URL is pinned to the one transfer endpoint (1.5 h)
- [x] Table `liquidity_construction_account_transfers`: deal; `transfer_direction` (`deposit_into_construction_account` / `steal_to_primary_checking`); amount; idempotency key (unique); Mercury transfer id; status; `requested_at`; `requested_by` (1 h)
- [x] `POST /liquidity/construction-accounts/{bought_deal_id}/deposit` and `/steal` (body: `amount_dollars`, `idempotency_key`; Steal also takes `confirm_amount_exceeds_safe_to_steal`). Guards:
  - `require_recent_auth` (the passkey step-up; the axios interceptor retries with the same body, so the same key);
  - source and destination come only from the stored link, never from the request;
  - 0 < amount ≤ the source's available balance;
  - Steal above safe-to-steal gives a 409 (naming the coming top-up) unless confirmed;
  - no transfer on a closed-out link;
  - a per-hour rate limit (`CONSTRUCTION_ACCOUNT_TRANSFERS_PER_HOUR`, default 5);
  - an audit row with the deal, the direction and the Mercury transfer id;
  - a successful Deposit marks the deposit row Done when `remaining_deposit` reaches 0 (3.5 h)

### Phase 7 — MCP support (2 h)
- [x] New GET endpoints (status, transactions, switch preview) become read-only tools automatically. Write tools on the app's own data are clearly described: link / settings, manual adjustments, transaction overrides, close-out marks, refresh. Unlink, delete-adjustment and switch are annotated destructive. `INSTRUCTIONS` gets the construction-account model, the formula and the manual controls in place of "stolen money" (1.5 h)
- [x] **The deposit and steal endpoints are NOT MCP tools**: add both to `EXCLUDED_TOOL_NAMES` (`mcp_server.py`), so Claude never moves money. Claude can still read the projection and safe-to-steal, and log manual entries. `test_mcp_tools.py` and `test_mcp_annotations.py` pin it (0.5 h)

### Phase 8 — Security task (2 h)
- [x] From `.claude/security.md`: *"Please check through all the code you just wrote and make sure it follows security best practices. make sure there are no sensitive information in the frontend and there are no vulnerabilities that can be exploited throughout all the code in this repo."* Specifically:
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
- [x] Goldens and regression snapshots in `Golden update:` commits; the README liquidity section, the routes table and the env-var table (`MERCURY_TRANSFER_API_TOKEN_<LABEL>`, `CONSTRUCTION_ACCOUNT_TRANSFERS_PER_HOUR`); check off this plan; push; open the PR (1 h)

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
