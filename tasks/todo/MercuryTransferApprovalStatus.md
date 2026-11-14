# MercuryTransferApprovalStatus: show when a Mercury transfer request is rejected or cancelled

Part B of the one branch `ConstructionAccountsCompactCardsAndRehabSummary` (one PR with `tasks/todo/ConstructionAccountsCompactCardsAndRehabSummary.md`). PR #129 is merged, so the branch starts from the latest `main` (`bdff7aa`).


## Context
Since #129 (merged), Deposit and Steal call `POST /api/v1/request-transfer`. The row is stored as follows:
- `transfer_outcome = "waiting_for_approval_in_mercury"`;
- `mercury_transfer_id` = the approval request's id, a uuid;
- `mercury_transfer_status = "pending_approval"`.

`_match_the_in_app_transfers_to_the_bank_feed` (`construction_accounts.py`) moves the row to `accepted_by_mercury` only when the bank transaction appears. If the request is rejected or cancelled in Mercury, no transaction ever comes, and the card shows "Approve it in Mercury" forever.

## Todo
- [x] Create the shared branch from the latest `main` and commit both plans (10 min)
- [x] **Verify the endpoint** (time-boxed, 15 min):
  - Look up `GET /api/v1/request-transfer/{requestId}` and its response shape (`requestId` / `id`, `status` values) on docs.mercury.com ("Get transfer approval request"). That site was unreachable from this session last time.
  - Mercury's connector tool `getTransferMoneyApprovalRequest` confirms `requestId` is a uuid. If the docs can't be read, code defensively and say "not verified against the docs" in the PR.
  **Result (2026-11-13).** docs.mercury.com is blocked from this session (proxy refusal), so the page wasn't read. What is confirmed:
  - Mercury's own connector: the get-by-id tool `getTransferMoneyApprovalRequest` takes `requestId` (a uuid), and the status enum is `pendingApproval` / `approved` / `rejected` / `cancelled`.
  - A live read-only list call: each request carries top-level `requestId` and `status`.
  - The path `GET /api/v1/request-transfer/{requestId}` mirrors the documented `GET /request-send-money/{requestId}`; it is **inferred, not verified**. A wrong path answers an error status, which leaves the row as it is.
- [x] **`BL/liquidity/common/mercury_transfers.py`**: add `fetch_transfer_approval_request_status(mercury_workspace_label, transfer_approval_request_id) -> str` (40 min):
  - `TRANSFER_APPROVAL_REQUEST_URL_TEMPLATE = f"{MERCURY_API_BASE}/request-transfer/{{}}"`. The id must fully match a uuid pattern, or it raises `MercuryApiError` before any call.
  - `_transfer_token_of_workspace` gives a `Secret`, wiped in `finally`; the bearer header only; `MERCURY_TIMEOUT_SECONDS`; no retry.
  - Errors: a `requests` exception, an HTTP error status (401/403 when the scope is missing) or a body that isn't JSON raise `MercuryApiError`. Only the class name or the HTTP status is logged, never Mercury's text.
  - The status comes from `_answer_of(body).mercury_transfer_status`, the existing normaliser (`pendingApproval → pending_approval`, `approved`, `rejected`, `cancelled`, else `unknown`).
- [x] **`construction_accounts.py`**: a new `_settle_the_in_app_transfers_rejected_or_cancelled_in_mercury(db, mercury_workspace_label) -> bool`, called in `refresh_one_workspace` after the per-link loop. A `True` result sets `construction_accounts_changed`, so `mark_construction_accounts_changed` runs and open pages reload (40 min):
  - It checks only the transfers of that LLC's linked, not-closed-out accounts with `transfer_outcome == waiting_for_approval_in_mercury` and a `mercury_transfer_id`. When nothing is waiting, it makes zero calls. It skips rows the feed has already matched (`seen_in_the_bank_feed_at` set).
  - `rejected` / `cancelled`: `transfer_outcome = failed_or_cancelled_at_mercury` and `mercury_transfer_status = <status>`. The function returns `True`.
  - `approved`: only `mercury_transfer_status = "approved"`, which returns `True` when it changed. The feed still counts the money when it arrives.
  - `pending_approval` / `unknown`: unchanged.
  - Any exception, including `MercuryTransferTokenMissingError`: catch it, log the class name, leave the row as it is, and move on. The refresh never fails because of this.
  - It runs only when the workspace was read from Mercury now (`workspace_read.was_read_from_mercury_now`), so it follows the shared pace and doesn't add calls on cached reads.
- [x] **Frontend `ConstructionAccountCard.vue`**: a small `transferOutcomeLabel(transfer)` (15 min):
  - `failed_or_cancelled_at_mercury` + `rejected` → "Rejected in Mercury"; + `cancelled` → "Cancelled in Mercury"; otherwise the existing label.
  - Optional: `waiting_for_approval_in_mercury` + `approved` → "Approved, waiting for Mercury to send it".
- [x] Run the checks (all pass; `verify_regression.py verify`: all snapshots identical, no golden update); if `python verify_regression.py verify` changes, run `snapshot` in a separate `Golden update: …` commit (20 min)

## Tests: none added, by request
Run the existing checks (the throwaway Postgres on 127.0.0.1:55432 via `BackEnd/docker-compose.test.yml`):
- `cd BackEnd && python -m pytest tests/test_mercury_transfers.py tests/test_liquidity_construction_account_transfers.py tests/test_liquidity_construction_account.py tests/test_mcp.py`
- `cd frontend && npx vue-tsc -b`

Existing tests mock `requests` and the transfer token. If a refresh test now meets a waiting transfer and makes an unexpected call, I fix the test's stub, not the behaviour.

## MCP
No new tool: transfers are never MCP tools. The refresh tool's behaviour is unchanged; it may now also settle rejected requests.

## Security (`.claude/security.md`)
"Please check through all the code you just wrote and make sure it follows security best practices. make sure there are no sensitive information in the frontend and there are no vulnerabilities that can be exploited throughout all the code in this repo". For this change:
- no token, secret or Mercury response text reaches the frontend or the logs;
- the token is wiped after use;
- the URL is pinned;
- the id is pattern-checked, so no path injection;
- no retry.

## Owner step
Add the "Fetch Transfer Money Requests" scope to each `MERCURY_TRANSFER_API_TOKEN_<LABEL>`. Until you do, the check gets 401/403 and leaves rows as they are.

