# Member Loan module (approved plan, revision 2)

Plan for branch `MemberLoan`, cut from `main`. Approved 2026-10-06 with the recommended defaults (see Resolution).

**Revision 2** (owner, 2026-10-06) has three parts:
1. Events can happen on any day.
2. Every event needs two-party approval.
3. Revised event types. **The owner's message was cut off inside this table**, at the `lender_withdrawal` row: "Amount only. Remove…". Only the visible part is applied, and it is marked *tentative*. The rest of section 3, and anything after it, is listed as open question Q1.

## Context

A signed loan agreement between Aviv Jan (Lender) and Big Whales AY LLC (Borrower) names this app as the deciding calculator. The module computes the balance exactly and keeps an append-only history with a full audit trail. Every change to the loan needs both members: one proposes and the other approves. The module produces monthly statements (PDF and CSV) and e-mails them on the 1st, and it e-mails both members at each step of an event's life. The statement PDF is the most important output. Anyone without financial background must be able to follow how the debt was reached.

**Timing.** The Effective Date is 2026-10-01. The first Interest Date and first statement e-mail are 2026-11-01.

## Decisions

| # | Decision | Status |
|---|---|---|
| D1 | New branch `MemberLoan` from `main`. | unchanged |
| D2 | Production is protected and both members have passkeys. The module still gates itself. | unchanged |
| D3 | For user actions, "today" comes from the device (Intl API) and is sent as an explicit date. The server never guesses "today" for a user action. The monthly cron uses America/New_York. | unchanged |
| D4 | After maturity, interest keeps accruing at 1% per month until repaid. | unchanged |
| D5 | When an event takes effect, both members get the notification e-mail: who proposed it and who approved it, the event type, effective date, amount, any written-agreement reference, and the before and after buckets. It is sent after commit. A failure is logged and never rolls back the change. | **changed by D16**: it now fires on *approval*, not on recording. "Both may record every event type" becomes "both may *propose*". |
| D6 | Past months are locked. | **under review**: see D15 and open question Q2 |
| D7 | A Yarden reduction is applied to Original Principal, then Capitalized, then Accrued. An amount above Amount Owed is rejected. | unchanged |
| D8 | All mail goes to the two addresses through Gmail SMTP. Addresses come from env only. | unchanged |
| D9 | Every event has its own effective date, plus an optional payment reference. | unchanged, reinforced by D15 |
| D10 | A cash election creates a non-compounding Interest payable line, cleared by withdrawals. | unchanged |
| D11 | An "interest-only" withdrawal takes Interest payable plus Accrued plus Capitalized. | **replaced (tentative)** by D17 |
| D12 | MCP excludes `/member-loan` entirely. | unchanged |
| D13 | A Render Cron Job is assumed. The owner checks the Postgres plan and backups. | unchanged |
| D14 | Lender capital credited may be negative. | unchanged |
| **D15** | **Events can fall on any calendar day.** Every day-of-month restriction is dropped. Interest is per diem from each event's effective date. | **new; replaces** the "advance must be on the 1st" rule from the original brief and from the event table |
| **D16** | **Two-party approval.** Either member may propose any event, reversals included. A proposal does not change the loan. Only the other member may approve or reject it, with a passkey session and step-up. The proposer may cancel while it is pending. Approval makes it take effect at its own effective date. | **new** |
| **D17** | `lender_withdrawal` takes **an amount only**. | **new, tentative** (truncated row). It removes the `interest_only` and `full_payoff` modes and so replaces D11. To be confirmed in Q1 |

### Derived rules

- **R1, day-count basis: 30/360, kept on purpose.** The agreement defines a full month as exactly 1% and a part month as 1/30 of 1% per day. Only a 30-day month gives that result in every month. Actual/365 would make February and 31-day months differ from 1%, which contradicts the agreement.
  - Rule: `day_position(d) = min(d.day, 31) − 1`, capped at 30. The next Interest Date is position 30. A period from `a` to `b` earns `balance × 1% × (position(b) − position(a)) / 30`.
  - **Visible consequences, stated in "How it works" and the PDF:**
    - An event on the 31st has zero interest days left in that month.
    - An event on Feb 28 has 3 interest days left (Feb 28, "29" and "30"). In a leap year, Feb 29 has 2.
    - A full month is always 30 days, so it always earns 1%.
- **R2, past-month lock: proposed change, decision pending (Q2).** The original reason for D6 was that a sent statement never changes. With any-day events and approvals that can cross a month end, a calendar lock would refuse legitimate approvals made on the 1st for events dated the 31st. **Recommendation, which replaces D6 and the old R1 and R2 once confirmed:** a month locks when its statement has really been sent, not at calendar midnight.
  - Before the send, events dated in that month may still be proposed and approved.
  - After it, any proposal, approval or reversal touching that month is refused.
  - Every sent statement stays final, and `ENGINE_VERSION` is still stored.
  - Until Q2 is answered, the engine and API implement the lock as one function, `month_is_locked(month)`, so either rule is a one-line switch.
  - The future-date limit (no more than New York today plus one day) is kept until Q3 says otherwise.
- **R3, the order buckets are used up.** A withdrawal is applied to Interest payable, then Accrued, then Capitalized, then Original Principal. A Yarden reduction is applied to Original Principal, then Capitalized, then Accrued, then Interest payable. *(unchanged)*
- **R4, rounding.** Each period's interest is rounded half-up to the cent when the period closes. The month's interest is the sum of those cent amounts. *(unchanged)*
- **R5, what the engine sees.** Only approved events whose reversal has not been approved. Order is by effective date, then by approval sequence on the same day. Pending, rejected, cancelled and expired events never change a figure.
- **R6, validation at approval.** Approval re-runs the whole engine with the event included. If any approved event becomes invalid, for example a later withdrawal would now exceed Amount Owed, the approval is refused with a plain message. Proposal runs the same check as a warning only.
- **R7, the preview guard.** The approval request carries the fingerprint (SHA-256) of the before and after preview the approver saw. If other approvals changed it in the meantime, the server returns 409 "figures changed, please review again" and the app shows the new preview. Whether that is enough is Q6.

## What the repo looks like (from exploration, unchanged)

- **Backend:** FastAPI, with layers `routers/` → `BL/` → `DAL/` and Pydantic in `ReqRes/common/`. Every number is `Decimal`. Postgres 16 on Render. New tables come from `create_all`; triggers go in idempotent `migrations/steps/`.
- **Frontend:** Vue 3, Vite, TS, Pinia, axios, Tailwind tokens and `Ui*` primitives. Netlify proxies `/api/*` to Render.
- **Reusable pieces:** passkey sessions, step-up (`require_recent_auth`), CSRF (`_csrf_problem`), and `routers/devices.py` as the model for a router that gates itself. Gmail SMTP (`BL/email/common/offer_email.py`), ReportLab PDFs (`BL/reports/common/deal_pdf.py`), and `mcp_server.py` (`DESCRIPTIONS`, `EXCLUDED_PREFIXES`).
- **Tests:** pytest on a throwaway loopback Postgres (`clean_database` deletes each table), `verify_regression.py`, Vitest and Playwright. Do not reuse `MoneyInput`: its shorthand reads a bare number under 1,000 as thousands, and it uses floats.

## Access gate (Phase 0, built first)

- Every `/member-loan/*` route resolves a real passkey web session whatever `AUTH_MODE` says.
  - No session gets 401.
  - A pending device gets 403.
  - An MCP or service session gets 403.
- The username must be one of exactly two in `MEMBER_LOAN_ALLOWED_USERNAMES`, which match `MEMBER_LOAN_LENDER_USERNAME` and `MEMBER_LOAN_YARDEN_USERNAME`. Anyone else gets 403 and is audited. A misconfiguration returns 503.
- **Every write (propose, approve, reject, cancel) needs CSRF and step-up.** There is a rate limit of 30 writes per hour per user.
- **An e-mail link alone never acts.** The links carry only the proposal id, open `/member-loan/approvals/<id>` and require a session.

## Calculation engine (pure, `Decimal`, whole cents)

`BL/memberLoan/common/member_loan_engine.py` has no DB, no FastAPI and no `float`.

- **Terms:** Effective Date 2026-10-01, Original Principal 30,410.00, 1% a month, maturity 2027-10-01 (informational). Interest continues after maturity.
- **Day count:** R1 (30/360).
- **Order on each day:** if it is an Interest Date, close the period and capitalize, or move the interest to Interest payable if cash was elected. Then apply that day's events in R5 order. Each event closes the current period (R4) and opens a new one at the new balance. That gives per-diem interest from the effective date (D15).
- **Inputs:** the effective events only (R5).
- **Buckets as of a date:** Original Principal, Capitalized Interest, Total Balance, Accrued Interest, Interest payable, Amount Owed and Lender capital credited.
- **Outputs:**
  - `summary(as_of)`.
  - `ledger_rows()`.
  - `monthly_statement(month)`: periods, the debt equation, plain sentences, warnings, and the count of pending or expired proposals left out.
  - `preview(candidate_event)`: before and after at the candidate's effective date, plus Amount Owed today. It is computed on the effective events, so it is always current.
  - `validate_with(candidate_event)` for R6.
- **`ENGINE_VERSION`** is stored on each sent statement.

## Event types

The `lender_withdrawal` row is tentative and the rest of the table is pending Q1. Rows the visible part of the owner's message did not touch are kept as they were, except that the day-of-month restriction is removed (D15).

| Event type | Effect when approved | Validation |
|---|---|---|
| `lender_withdrawal` | Applied per R3. *Tentative D17:* takes an amount only, with no interest-only or payoff modes. | Amount above 0 and no more than Amount Owed on the effective date. Any day. |
| `lender_additional_advance` | Original Principal plus amount, accruing from the effective date. | **Any day (D15; replaces "1st of a month").** Written-agreement date and description are required. |
| `yarden_capital_contribution_reduction` | Applied per D7 and R3. Capital credited plus amount. | Amount above 0 and no more than Amount Owed. Any day. |
| `yarden_additional_withdrawal_increase` | Original Principal plus amount. Capital credited minus amount. Carries the no-clause warning everywhere. | Written-agreement fields required. Any day. |
| `interest_payment_election` | `reinvest` or `cash` for one Interest Date. | The date is by nature an Interest Date (the 1st). It is the one date-bound type, because it names which capitalization it controls, not when money moves. Confirm in Q1. |
| `reversal` | Cancels one earlier **approved** event. It also needs approval (D16). While the reversal is pending, the original stays in effect. | The target is approved, not already reversed and not a reversal itself. Reason required. Subject to the lock (R2). |

Every type also takes an effective date, an optional note and an optional payment reference.

## Approval lifecycle (D16)

```
proposed ──approve (counterparty, step-up, fresh fingerprint)──▶ approved  ──▶ takes effect at effective date
    │──reject (counterparty, step-up, reason)──────────────────▶ rejected
    │──cancel (proposer, step-up)──────────────────────────────▶ cancelled
    └──(Q4/Q5) expiry or the month locks while pending──────────▶ expired
```

- **Who may act:** only the counterparty may approve or reject; the proposer gets 403. Only the proposer may cancel. A third person never reaches these routes.
- **One decision per event,** enforced by a unique index. A double click or a race returns 409.
- **Recommended defaults for open questions Q4 to Q6:**
  - A pending proposal expires 14 days after it was proposed, or when its month locks (R2), whichever comes first. The cron and every read record that lazily as a system `expired` decision.
  - An expired proposal can be re-proposed in one click, which creates a new proposal.

## Data model (new tables, all append-only and hash-chained)

- **`member_loan_events`** holds each **proposal**:
  - Identity and order: `id`, `proposal_sequence` (unique), `event_type`, `effective_date`.
  - Amount and choice: `amount` NUMERIC(14,2), `interest_election_choice`.
  - References: `written_agreement_date`, `written_agreement_description`, `payment_reference`, `reverses_event_id`, `reversal_reason`, `note`.
  - Provenance: `proposed_by_user_id`, `proposed_by_username`, `proposed_at`, `request_ip`.
  - Preview: `preview_at_proposal` (JSON) and `preview_fingerprint_at_proposal`.
  - Tamper evidence: `previous_event_hash` and `event_hash`.
  - **Change from revision 1:** `withdrawal_mode` is removed (D17, tentative), and `recorded_*` is renamed `proposed_*`.
- **`member_loan_event_decisions`** is **new**. It records the state change without ever updating the event row:
  - `id`, `decision_sequence` (unique), `event_id` (**unique**, so there is one decision per event).
  - `decision`: `approved`, `rejected`, `cancelled` or `expired`.
  - `decided_by_user_id`, `decided_by_username` (`system` for expiry), `decided_at`.
  - `decision_reason`, `preview_fingerprint_confirmed` and `preview_at_decision` (JSON).
  - `previous_decision_hash` and `decision_hash`.
  - An event's state is `pending` while it has no decision row, otherwise the decision. The approver, timestamps and state are all in the hash chain.
- **`member_loan_audit_entries`**: the actions are now:
  - `event_proposed`, `event_approved`, `event_rejected`, `event_cancelled`, `event_expired`.
  - `proposal_notification_sent` and `proposal_notification_failed`.
  - `decision_notification_sent` and `decision_notification_failed`.
  - `statement_sent`, `statement_dry_run` and `statement_send_failed`.
  - Each row keeps `state_before` and `state_after` (the effective buckets), actor, IP and its hash chain. Each proposal or decision commits in the same transaction as its audit row.
- **`member_loan_statement_sends`**: unchanged. It also records the count of pending or expired proposals left out.
- **Append-only:** row triggers refuse UPDATE and DELETE on events, decisions and audit entries. On sends, only the update out of `sending` is allowed. `GET /member-loan/integrity` verifies every chain. Tests use TRUNCATE for these tables; the isolation guard is untouched.

## API (`routers/member_loan.py`, all self-gated)

| Endpoint | Purpose |
|---|---|
| `GET /member-loan/access` | Role, and how many proposals are waiting for the caller. |
| `GET /member-loan/summary?as_of_date=` | Effective buckets. The date is required. |
| `GET /member-loan/ledger` | Effective events, Interest Date rows, and who proposed and approved each. |
| `POST /member-loan/events` | **Propose** an event. Step-up. Returns the pending proposal and its preview. |
| `POST /member-loan/events/{id}/reversal` | **Propose** a reversal. Step-up. |
| `GET /member-loan/events?state=pending\|approved\|rejected\|cancelled\|expired` | Proposals with a live preview and fingerprint. |
| `GET /member-loan/events/{id}` | One proposal: live preview, preview at proposal, and what changed since. |
| `POST /member-loan/events/{id}/approval` | Approve. Body: `preview_fingerprint`. Counterparty only, step-up, R6 and R7. |
| `POST /member-loan/events/{id}/rejection` | Reject. Body: `reason`. Counterparty only, step-up. |
| `POST /member-loan/events/{id}/cancellation` | Cancel. Proposer only, step-up. |
| `GET /member-loan/statements/{yyyy-mm}` and `.../pdf` | Statement figures and PDF. |
| `GET /member-loan/ledger.csv` | Ledger CSV, with the injection guard. |
| `GET /member-loan/audit` | Audit entries. |
| `GET /member-loan/integrity` | Hash-chain check. |
| `GET /member-loan/explanation` | The formulas text. |

## Notifications (all after commit, failures audited, never rolled back)

| Trigger | To | Content |
|---|---|---|
| Proposed (event or reversal) | **The other member** | Who proposed it, type, effective date, amount, agreement reference, payment reference, the before and after preview, and a link to `/member-loan/approvals/<id>` with no token. The link explains that approving needs a passkey sign-in. |
| Approved | Both | The D5 content, plus proposer, approver and approval time. |
| Rejected | Both | The event details, who rejected it, and the reason. |
| Cancelled | Both | The event details and who cancelled it. |
| Expired (if Q4 keeps expiry) | Both | The event details, the reason (14 days, or its month locked) and how to re-propose. |

## Statement PDF: simple and fully explanatory

The six-section layout is unchanged. Only effective (approved) events appear.

1. **Summary box:** opening Total Balance, interest this month, number of events, closing Total Balance, Amount Owed.
2. **What happened this month:** one sentence per event, now including the approval. For example: "Dec 15 – Aviv withdrew $1,000.00 (proposed by Aviv on Dec 15, approved by Yarden on Dec 16). It was taken from accrued interest ($144.77), then capitalized interest ($611.24), then principal ($243.99)." An event on a day other than the 1st needs no special wording. The interest periods show its effect.
3. **How the interest was calculated:** one line per period, for example "Jan 10 – Feb 1: $36,331.45 × 1% × 21/30 = $254.32". Then the sum. A Feb 28 or 31st event shows its 30/360 days.
4. **How the total debt was calculated:** the step-by-step equation, then Amount Owed.
5. **How it works:** 1% a month, every month counted as 30 days, with the 31st and Feb 28 consequences in one sentence. Interest is added on the 1st. It stops or starts on the event date. Every change needs both members.
6. **Footer:**
   - Warnings: a Yarden increase with no clause in the agreement, and "N proposed events were still waiting for approval and are not included".
   - The binding 30-day sentence, the engine version and the ledger hash.

A test re-parses the PDF and asserts every printed equation adds up.

## Monthly statement e-mail (unchanged except the lock)

- **Command:** `manage.py send-member-loan-statement`. It is idempotent, has a dry-run default and `--retry-failed`, and runs as a Render Cron Job at `CRON_TZ=America/New_York 13 6 1 * *`.
- **With R2 as recommended,** a successful real send is what locks the month. In the same run it expires any still-pending proposals dated in that month and e-mails both members about them.

## Frontend: plain words

- `views/MemberLoan.vue` has these tabs:
  - **Today:** Amount Owed and buckets, as of the device date.
  - **Waiting for approval:**
    - "Waiting for you": each item has the live before and after, a "changed since it was proposed" note when relevant, and Approve or Reject with step-up and a reason box.
    - "Waiting for the other member": your own proposals, each with a Cancel button.
  - **History:** ledger rows with proposer and approver, plus CSV download.
  - **Propose a change:** one form per type, any day. The default date is the device date. A preview runs before submitting. The button reads "Send to <other member> for approval".
  - **Statements**, **How it works** and **Audit**.
- `/member-loan/approvals/:id` deep-links from the e-mail and opens the approval card after sign-in.
- The nav badge shows how many proposals wait for you.
- Amounts are strings end to end. `LoanAmountInput` is strict. The frontend does no loan math.

## Security task (`.claude/security.md`)

> "Please check through all the code you just wrote and make sure it follows security best practices. make sure there are no sensitive information in the frontend and there are no vulnerabilities that can be exploited throughout all the code in this repo"

On top of the earlier checklist:
- Only the counterparty can approve, enforced server-side.
- E-mail links carry no token and never act on their own.
- The fingerprint prevents approving figures you were not shown.
- A unique index makes double decisions impossible.
- The decision table is append-only and hash-chained.
- Then the repo-wide pass, with findings in Review.

## Todo (agent wall-clock)

- [x] **0** (10 min): Branch `MemberLoan` from `main`, copy this file to `tasks/todo/MemberLoan.md`, set up the test Postgres and dependencies.
- [x] **1** (45 min): Engine core: 30/360 positions, any-day periods, R4 rounding, capitalization, Interest payable, post-maturity accrual.
- [x] **2** (60 min): Engine events: withdrawal (amount only), advance on any day, Yarden reduction and increase, election, reversal, R5 ordering, validation, `validate_with` (R6).
- [x] **3** (45 min): Engine outputs: summary, ledger, statement (periods, equation, sentences, left-out count), preview and fingerprint, explanation.
- [x] **4** (50 min): Models: events, **decisions**, audit, sends. Append-only triggers, hash chains, crud, TRUNCATE in tests.
- [x] **5** (45 min): Access gate, step-up, CSRF, rate limit.
- [x] **6** (60 min): Propose and reversal-propose endpoints, read endpoints, the lock function (R2).
- [x] **7** (60 min): **Approve, reject and cancel**: counterparty and proposer rules, R6 and R7, unique decision, expiry (Q4 default).
- [x] **8** (50 min): Notifications: the proposal e-mail to the counterparty with link; approved, rejected, cancelled and expired e-mails to both; audit rows.
- [x] **9** (70 min): Statement PDF, six sections with approval wording. Ledger CSV.
- [x] **10** (50 min): `send-member-loan-statement`: idempotent, dry run, retry-failed, lock and expiry on send.
- [x] **11** (15 min): MCP: exclude `/member-loan`, add `DESCRIPTIONS`.
- [x] **12** (130 min): Frontend: view, store, API, types, `LoanAmountInput`, tabs including **Waiting for approval**, the approval deep link, nav badge.
- [ ] **13** (20 min): Regression snapshot. A `Golden update:` commit if needed.
- [ ] **14** (40 min): Security task.
- [ ] **15** (25 min): README: the module, the approval flow, env, Render Cron, America/New_York, 30/360 consequences, the Postgres backup check, the stale "no auth" line. Review section.
- [ ] **16** (15 min): Push `MemberLoan` and open the PR.

Total is about 13 hours, up from 11.

## Tests

### Unit (`tests/test_member_loan_engine.py`, effective events only)

Values were computed with Python `Decimal` under R1 and R4.

| Case | Expected |
|---|---|
| No events, 2026-11-01 | interest 304.10, Total Balance 30,714.10 |
| No events, 2026-12-01 | interest 307.14, Total Balance 31,021.24 |
| No events, 2027-01-01 | interest 310.21, Total Balance 31,331.45 |
| No events, as of 2026-12-15 | Accrued 144.77, Amount Owed 31,166.01 |
| As of 2026-10-31 | Accrued 304.10 (30/30) |
| As of 2027-02-28 | Accrued 284.80. 2027-03-01 interest 316.45, Total Balance 31,961.21 |
| Leap year (terms 2028-02-01, $10,000) | as of 2028-02-29 Accrued 93.33. 2028-03-01 interest 100.00 |
| Withdrawal $1,000 on 2026-12-15 | from accrued 144.77, capitalized 611.24, principal 243.99. Total Balance 30,166.01. 2027-01-01 interest 160.89, Total Balance 30,326.90 |
| **Withdrawal $1,000 on 2026-10-31** (new) | from accrued 304.10, principal 695.90. Total Balance 29,714.10. 2026-11-01 nothing left to capitalize. 2026-12-01 interest 297.14 |
| Withdrawal $500 on 2026-11-01 | Total Balance 30,214.10. 2026-12-01 interest 302.14 |
| Yarden reduction $5,000 on 2026-12-15 | periods 144.77 + 138.78. 2027-01-01 interest 283.55, Total Balance 26,304.79. Capital credited 5,000.00 |
| Yarden reduction above Original Principal | spills into Capitalized, then Accrued |
| Yarden reduction above Amount Owed | rejected |
| Yarden increase $2,000 on 2026-12-15 | periods 144.77 + 176.11. 2027-01-01 interest 320.88, Total Balance 33,342.12. Capital credited −2,000.00. Warning |
| Advance $5,000 on 2027-01-01 | Total Balance 36,331.45. 2027-02-01 interest 363.31, Total Balance 36,694.76 |
| ~~Advance not on the 1st is rejected~~ | **replaced (D15):** |
| **Advance $5,000 on 2027-01-10** (new) | periods 93.99 (9/30 on 31,331.45) + 254.32 (21/30 on 36,331.45). 2027-02-01 interest 348.31, Total Balance 36,679.76 |
| **Advance $1,000 on 2026-10-31** (new, 31st) | periods 304.10 + 0.00 (0 days left). 2026-11-01 interest 304.10, Total Balance 31,714.10 |
| **Advance $1,000 on 2027-02-28** (new) | periods 284.80 (27/30) + 32.64 (3/30 on 32,644.76). 2027-03-01 interest 317.44, Total Balance 32,962.20 |
| Cash election for 2026-11-01 | Interest payable 304.10, Total Balance 30,410.00. 2026-12-01 interest 304.10 |
| ~~Interest-only withdrawal~~, ~~full payoff mode~~ | **removed (tentative D17).** Replaced by: a withdrawal equal to Amount Owed sets every bucket to 0, and interest stays 0 afterwards |
| Withdrawal above Amount Owed | rejected |
| After 2027-10-01 | interest continues at 1% |
| Pending, rejected, cancelled or expired event | figures identical to having no event (R5) |
| Reversal pending | original still in effect. Reversal approved: figures equal the case without the event |
| Two events on the same day | applied in approval order (R5) |
| R6 | approving an earlier withdrawal that makes a later approved withdrawal exceed Amount Owed is refused |
| Preview fingerprint | changes when another approval changes the before or after state, and is stable otherwise |
| Rounding | half-up. No `float` in the module |
| Statement equations | every period line and the debt equation add up for each case above |

### Integration (pytest, test Postgres)

- **Gate:** as before (401 in every `AUTH_MODE`; 403 for a third user, MCP or pending device; 503 on bad config; step-up, CSRF and rate limit).
- **Approval:**
  - A proposal leaves the summary unchanged.
  - The counterparty approves and the summary changes at the effective date.
  - The proposer approving their own event gets 403.
  - Approval without step-up gets `reauth_required`.
  - A second decision gets 409 from the unique index.
  - A stale fingerprint gets 409.
  - Rejection requires a reason.
  - Cancel by a non-proposer gets 403. Cancel after a decision gets 409.
  - A reversal needs approval, and the original stays in effect while it is pending.
  - Expiry after 14 days writes a system decision (Q4 default).
  - Approval refused by R6.
- **Lock (implementing the R2 recommendation, adjusted to the Q2 answer):**
  - Before the month's statement is sent, an event dated in it can be proposed and approved.
  - After a real send, proposing, approving or reversing into that month gets 422, and its pending proposals expire.
  - A dry run does not lock.
  - A date after New York's today plus one day gets 422.
- **Append-only:** raw UPDATE and DELETE on events, decisions and audit raise. A tampered row of any of them breaks integrity.
- **Audit:** each proposal or decision has exactly one audit row in the same transaction, with correct before and after state.
- **Notifications:**
  - A proposal mails only the other member, with a token-free link and the preview.
  - Approval mails both with the D5 content plus approver.
  - Rejection and cancellation mail both. Expiry mails both.
  - An SMTP failure keeps the state and writes a `*_notification_failed` row.
- **Statements:** figures match the engine. The PDF has the six sections, approval wording, the left-out count, the binding sentence and warnings. Every equation adds up.
- **CSV, cron command, MCP and regression:** as before.

### E2E (Playwright, two browser contexts each with its own virtual authenticator)

- Aviv proposes a mid-month withdrawal. The figures are unchanged. Yarden sees "Waiting for you", approves through step-up, and the ledger and Amount Owed update.
- Yarden proposes an advance on the 10th and Aviv rejects it with a reason. Nothing changes and the reason appears in History.
- Aviv proposes and then cancels.
- A Yarden increase is blocked without agreement fields. Once approved, the statement shows the warning.
- The deep link `/member-loan/approvals/<id>` asks for sign-in, then opens the card.
- PDF and CSV download. A non-allowed user gets a 403. Axe and CSP pass.

## Verification

1. Backend:
   ```
   cd BackEnd && pytest && python3 verify_regression.py verify
   ```
2. Frontend:
   ```
   cd frontend && npm test && npm run build && npm run verify:ui -- --fast && npm run e2e
   ```
3. Dry run, then review the e-mail and PDF by hand:
   ```
   python manage.py send-member-loan-statement --month 2026-10 --dry-run
   ```
4. After deploy: run one real propose, approve and notify cycle between the two members on a small test amount, then reverse it the same way. Keep the statement dry run on until the owner approves the first real send.

## Resolution (owner approved the plan, 2026-10-06)

The owner approved the plan without further answers, so each open question takes its recommended default:

- **Q1:** tentative D17 stands. A withdrawal takes an amount only, and the other types are as in the table. A resent section 3 is applied as a follow-up.
- **Q2:** a month locks when its statement is really sent. This replaces D6.
- **Q3:** an effective date may be at most New York's today plus one day. Scheduled future events are not built.
- **Q4:** a pending proposal expires after 14 days, or when its month locks.
- **Q5:** a pending proposal in a month that locks expires automatically and can be re-proposed in one click.
- **Q6:** the approver confirms the live preview through the fingerprint (R7). There is no automatic cancellation.
- **Q7:** only the other member receives the proposal e-mail.
- **Q8:** a rejection reason is required.

Execution order follows the Todo list. Each item is checked off in `tasks/todo/MemberLoan.md` as it lands.

## Open questions for the owner (resolved above; kept for the record)

1. **Q1, section 3 was cut off.** Your message ends at the `lender_withdrawal` row ("Amount only. Remove…"). Please resend the full revised event-type table and anything after it. Until then:
   - `lender_withdrawal` takes an amount only, and the interest-only and payoff modes are removed (tentative D17, replacing D11).
   - The other types are kept with the day-of-month limit removed.
   - The interest election stays tied to an Interest Date.
2. **Q2, past-month lock.** Should a month lock (a) when its statement is really sent, which is recommended and replaces D6, (b) at calendar month end as in D6, or (c) never, which would bring back "Restated" statements?
3. **Q3, future-dated events.** "Takes effect at its own effective date" could mean you want to schedule future events, such as an advance next week. Should future effective dates be allowed, and how far ahead? The current limit is New York today plus one day.
4. **Q4, expiry.** Should pending proposals expire? The recommendation is 14 days or when their month locks, whichever comes first, and either member can re-propose in one click.
5. **Q5, a pending event in a locked month.** If its month locks while it is still pending, should it expire automatically (recommended) and be re-proposed with a current date? Or should it stay pending and be unapprovable?
6. **Q6, a changed preview.** If other approvals change the figures while a proposal waits, is it enough for the approver to see and confirm the new preview (the R7 fingerprint, recommended)? Or should the proposal be cancelled automatically and need the proposer to re-propose?
7. **Q7, the proposer's copy.** On proposal, should the proposer also get a copy of the e-mail sent to the other member? Currently only the other member gets it.
8. **Q8, notification wording.** Should rejection reasons be required, as planned, or optional?
