# Fix: ARV estimates fail behind Netlify's proxy timeout. Run them as a background job the popup polls

Branch: `claude/admiring-fermi-pqek7t`, restarted from main after #97 merged.

## Context (diagnosed from the user's DevTools screenshot and the Render logs)
- **The path:** production calls the API through Netlify's `/api/*` → Render rewrite (`frontend/public/_redirects`),
  so session cookies stay first-party.
- **What happened (Render logs, 2026-10-11):**
  - 18:36:42 `POST /arv-estimate` got a 401 because the access cookie had expired. This is normal: the axios
    interceptor refreshed at 18:36:43 (200) and retried.
  - The retried request ran on the backend. Claude answered at 18:37:39 (56 s) and again at 18:39:29 (~2m50s).
  - The browser had already given up after about 30 s. Netlify's proxy cuts off long responses and returns a
    non-JSON error, so the popup showed the generic "The ARV estimate failed; try again."
- **Consequences:**
  - Every real estimate will fail through Netlify. The API credit is still spent and the result is thrown away.
  - Real estimates take 1–3+ minutes, not the "30–90 s" the popup says.
- **Goal:** no single HTTP request runs longer than a few seconds.

## Design: start a job, then poll it
### Backend
- **New `BL/arvEstimate/common/arv_estimate_jobs.py`:** an in-memory job registry. The service has one Render
  instance (`numInstances: 1`), so no DB table or migration is needed.
  - `ArvEstimateJob` holds `arv_estimate_job_id` (uuid4 hex), `status` (`RUNNING|SUCCEEDED|FAILED`),
    `arv_estimate`, `failure_message`, `created_at` and `deal_type`.
  - Jobs run on a module-level `ThreadPoolExecutor(max_workers=2)` that calls the existing
    `estimateArv.estimate_arv_with_claude`. `ArvEstimateFailedError` / `ArvEstimateNotConfiguredError` become a
    FAILED job carrying the safe message. Any other exception gets a generic message and a logged ref.
  - Finished jobs are pruned after 30 minutes. A dict access guarded by a `threading.Lock` is enough.
  - A redeploy loses running jobs. The poll then gets a 404, and the popup says "The estimate was interrupted
    (server restarted); try again."
- **Routes (`routers/arv_estimate.py`):**
  - `POST /arv-estimate`:
    - Keeps the rate limit and audit, both counted at start.
    - Checks the key up front, so 503 "not configured" stays immediate.
    - Submits the job and returns **202** `ArvEstimateJobRes {arv_estimate_job_id, status: "RUNNING"}`.
  - New `GET /arv-estimate/{arv_estimate_job_id}`:
    - Returns `ArvEstimateJobRes {arv_estimate_job_id, status, arv_estimate | null, failure_message | null}`.
    - Answers 404 for an unknown or expired id.
    - Gated like every data route (it is in the same router).
  - Schemas go in `ReqRes/common/arv_estimate_schemas.py`. `ArvEstimateRes` is unchanged.
- **MCP:** the routes become two tools.
  - `estimate_arv_with_claude` now says "starts a job; poll get_arv_estimate_job".
  - The new GET tool needs a description in `DESCRIPTIONS` (max 400 characters). It is read-only and not
    open-world.
- **Regression snapshot:** re-record. The diff should be the `/arv-estimate` response change plus the new path and
  schema. The PR is not merged, so main's contract is unaffected.

### Frontend
- **`api/index.ts`:**
  - `startArvEstimateWithClaude(req)` (POST) and `getArvEstimateJob(id)` (GET).
  - `estimateArvWithClaude(req)` keeps its signature and does the start-then-poll loop: every 3 s, up to 6
    minutes. It returns `ArvEstimateRes`, or throws an error whose `response.data.detail` is the job's
    `failure_message`, so the popup's error handling stays unchanged.
  - The poll interval and the overall limit are named constants.
  - The 401-refresh interceptor already covers the polls.
- **Popup:**
  - The loading copy becomes "Claude is pulling comps and adjusting them — usually 1–3 minutes. You can keep this
    open."
  - The generic error includes the HTTP status when there is one: "The ARV estimate failed (HTTP 504); try
    again." A future failure is then diagnosable from the UI.
  - An overall poll timeout says "Claude is still working after 6 minutes; try again later."

## Tests
- **Unit (pytest):**
  - The job registry: success, a failed estimate keeps the safe message, an unexpected exception gets the generic
    message, expired jobs are pruned.
  - Use a synchronous executor stub so tests are deterministic.
- **Integration (pytest TestClient):**
  - POST returns 202 with a job id; GET then shows SUCCEEDED with the template (fake BL).
  - FAILED carries the message. An unknown id is 404.
  - 503 without a key. 429 over the limit. Both routes are behind the gates.
- **MCP:**
  - Both tools are listed with the right annotations.
  - Start, then get, round-trips.
- **Vitest:**
  - The `estimateArvWithClaude` poll loop with fake timers: RUNNING → SUCCEEDED, FAILED → throws with the detail,
    404 → "interrupted".
  - The popup shows the status code in the generic error.
- **Playwright:** mock both routes (POST → 202 job, GET → RUNNING once, then SUCCEEDED). The existing three specs
  are updated, including the real-backend 503.
- **Security task (`.claude/security.md`):**
  - The job ids are uuid4 and unguessable.
  - The GET sits behind the same app-key and session gates.
  - The failure messages are the existing safe strings.
  - Re-run bandit, pip-audit, npm audit and the `security-review` skill.

## Verification
- Full pytest suite, `verify_regression.py verify` after the re-record, vitest, vue-tsc, the Playwright spec.
- After the merge or deploy, the user retries on bigwhales.netlify.app:
  - DevTools should show one fast POST (202) and then GET polls every 3 s.
  - Render logs should show the Claude calls and the final GET returning SUCCEEDED.

## Todo
- [x] J1 (40 m) Job registry `BL/arvEstimate/common/arv_estimate_jobs.py`, job schemas.
- [x] J2 (30 m) POST returns 202 + job id; new GET; MCP descriptions; snapshot re-record.
- [x] J3 (40 m) Backend tests (unit, route, MCP).
- [x] J4 (40 m) Frontend start + poll in `api/index.ts`, popup copy and status-coded error, vitest.
- [x] J5 (30 m) Playwright spec on the two mocked routes plus the real 503.
- [x] J6 (20 m) Security task: bandit, pip-audit, npm audit, `security-review`.
- [x] J7 (10 m) Push, open the PR.
