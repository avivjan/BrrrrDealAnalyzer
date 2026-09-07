# Security Phase 3 — device allowlisting and hardening

Same branch and PR as Phases 0–2 (`claude/security-phase-0-yxjnsp`, PR #44). Scope:
`SECURITY_PLAN.md` §3.4 (Pillar 3), §3.5 (cross-cutting) and roadmap Phase 3. Everything
stays behind the Phase 2 flags: with `AUTH_MODE=off` the site has no session, the new
`/settings/devices` page is simply not linked, and nothing else moves.

## Plan

- [x] **P3.1** (2 d) — `routers/devices.py`: `GET /devices/me` (pending sessions allowed),
      `GET /devices`, `PATCH /devices/{id}` (rename), `POST /devices/{id}/approve`,
      `POST /devices/{id}/revoke` (device + all its sessions + refresh family), `GET /sessions`,
      `DELETE /sessions/{id}`, `GET /credentials`, `DELETE /credentials/{id}` (refuses the
      last one). Approve, revoke and credential delete need a fresh passkey prompt (step-up).
      Excluded from MCP tools (the prefixes are already on the exclusion list).
- [x] **P3.2** (0.5 d) — Step-up on deliberate actions: `require_step_up` — a no-op unless
      `AUTH_MODE=enforce`; MCP sessions are exempt (the device approval is the human in the
      loop); applied to `/send-offer`. The SPA answers `reauth_required` with one passkey
      prompt and retries (axios interceptor), so the feature is unchanged apart from the prompt.
- [x] **P3.3** (2.5 d) — `SettingsDevices.vue` at `/settings/devices`: devices (kind badge,
      approve / revoke / rename), sessions (end one, end all others), passkeys (delete except
      the last, "add a passkey on another device" link), pending-approval banner. Linked from
      the appearance drawer only when a session exists.
- [x] **P3.4** (0.5 h) — CSP: `Content-Security-Policy-Report-Only` → enforcing in
      `frontend/public/_headers`, proven by a Playwright check that injects the exact header
      on every document response and walks every route asserting zero violations.
- [x] **P3.5** (0.5 d) — `DEVICE_POLICY` rollout notes and the `/pending` page wired to the
      approval (poll → `trusted` → continue).
- [x] **P3.6** (1 d) — Tests: `tests/test_devices.py` (pending blocked, approve promotes,
      revoke kills sessions and tools, last credential undeletable, step-up required, MCP
      device revocation), `SettingsDevices` unit test, Playwright `checks/csp.spec.ts` and the
      devices flow on the virtual authenticator.
- [x] **P3.7** (1 d) — Final re-audit of the branch against `SECURITY_PLAN.md`'s matrix (each
      finding: fixed / mitigated / deferred with reason), README, this file, PR description.

Deferred, with reason: F-20 numeric `Field(ge/le)` bounds on the persist schemas — an
autosaving draft may legitimately hold a zero or blank number the calculator rejects, so a
bound there would refuse records that save today; the calculator's own 400s are unchanged.
Optional e-mail notice for pending devices and the WebCrypto device key (v2 options) are not
built.

## Tests

- Backend: `pytest` (whole suite + `test_devices.py`); `verify_regression.py verify` after
  one deliberate re-record (the `/devices*`, `/sessions*`, `/credentials*` operations).
- Frontend: `npm test`, `npm run build`, Playwright chromium (`checks/csp.spec.ts`,
  `checks/auth.spec.ts` extended with device approval), `verify:ui --fast`.
- Static: `pyflakes`.

## MCP server

`/devices/*`, `/sessions/*`, `/credentials/*` are excluded from tool generation: an LLM must
not approve or revoke devices. MCP connectors (path-secret and OAuth) appear in the devices
list with kind `mcp`; revoking one there stops all its tools (`test_devices.py`).

## Security (`.claude/security.md`)

- [x] No secret in any file; the dashboard never shows a token, only ids, labels, platforms,
      times and the last IP.
- [x] Every mutating dashboard call needs a trusted session, the CSRF headers and a recent
      passkey assertion; a user can only see and manage their own sessions and passkeys,
      while any trusted owner can approve or revoke any device (two-person business, O-7).
- [x] CSP enforced with no `unsafe-eval`; `frame-ancestors 'none'`.

## Review

**What changed.** `routers/devices.py` (10 operations, self-gated, excluded from MCP tools);
`require_step_up` on `/send-offer` (a no-op unless `AUTH_MODE=enforce`, MCP sessions exempt);
the SPA's `/settings/devices` dashboard, the one-line `SecurityBar` above every page while a
session exists, and a `reauth_required` → one passkey prompt → retry rule in the axios
interceptor; the Content-Security-Policy is enforcing. `main.py` only grew the `devices`
router in `PUBLIC_ROUTERS` (it checks the session itself so `/devices/me` can answer a
pending browser). No existing operation, schema or calculation changed.

**Functional invariants held.** Backend 433 passed (+15 `test_devices.py`);
`verify_regression.py verify` identical after the one deliberate re-record (the new
operations only); vitest 87 files / 1379 tests; `npm run build`; Playwright chromium
104 passed / 3 skipped — the new `checks/csp.spec.ts` walked every route under the exact
production CSP with zero violations, and `checks/auth.spec.ts` now also exercises the
dashboard (rename, sessions, passkeys, the enrollment link, sign-out from the list).
`verify:ui --fast`: G6 green; the UI-overhaul gates fail on `main` identically (see Phase 2).

**Decisions worth knowing.**
- Any trusted owner approves or revokes any device (O-7 default); sessions and passkeys are
  per person. Revoked browsers leave the list, revoked connectors stay visible.
- The dashboard link lives in a strip rendered by `App.vue` rather than the appearance
  drawer, whose unit test forbids store imports; it renders nothing without a session.
- A pending-device count is shown on the dashboard (banner), not polled into the nav: no
  extra request on ordinary pages, so the feature goldens are untouched.
- F-20 numeric bounds on the persist schemas are deferred (an autosaving draft may hold a
  zero the calculator rejects; refusing it would be a regression). The calculator's own
  400s are unchanged.

**Re-audit of the matrix (SECURITY_PLAN.md §2), branch head.** Fixed: F-01 (sessions,
enforce flag), F-02, F-03 (session on /reps, tab kept), F-04, F-05, F-06, F-07, F-08, F-09,
F-10, F-11 (CSP enforcing), F-12, F-14 (credentials only with an explicit origin list),
F-15 (ReportLab escape was already in place), F-16 (pins, Dependabot, CI audits),
F-17 (`sslmode=require`), F-18 (`.env.example`), F-19 partially (prod console logging still
prints routes; low), F-22, F-23, F-24, F-25, F-26, F-28. Mitigated by configuration the
owner performs (documented in the README / plan, not code): F-13 SA scope narrowing and
key rotation, F-21 Mercury read-only tokens + IP allow-list, F-27 README wording after
the OAuth switch. Deferred: F-20 (above).

**Rollout for this phase.** Nothing to flip for the dashboard; `DEVICE_POLICY=log` for a
while, then `enforce` once both owners' browsers show as trusted. Rollback = the env flip.


## Merge with `main` (after Phase 3)

`main` gained PR #45 (compact MCP deal tools, `routers/deals.py`) and PR #46 (calculator audit
fixes F1–F10) while this branch was in flight. Merged, three conflicts resolved: the router
registry keeps `deals` (before `auth`/`devices`, so main's OpenAPI order holds), `mcp_server.py`
keeps the plan's `tool_annotations` (main's inline annotations were a subset; main's new
`test_annotations_follow_the_http_method` now also accepts the F-24 irreversible set as
destructive), and the OpenAPI snapshot was re-recorded. The new `/deals/*` routes sit behind the
same gates as every other data router. Backend 499 passed, vitest 1383, build green.

Playwright on the merged tree: 95 passed, 9 failed — all nine are network goldens whose
calculation breakdown gained main's new "Rehab float buffer (10% of rehab)" step (PR #46 changed
the calculator without re-recording `frontend/e2e/golden`). Not this branch's change and not
touched here: the goldens follow the repo's "Golden update:" commit convention, for the owner
to re-record once PR #46's numbers are confirmed as intended.
## Independent review before merge

Four adversarial reviewers (a general sweep plus deep dives on sessions/devices, the MCP and
OAuth path, and the frontend/CSP/data hardening) read the branch at `1b4ca30` with main frozen.
Everything they found was verified against the code and fixed on the branch; nothing was left
as a follow-up.

| # | Finding | Severity | Fix |
|---|---|---|---|
| R1 | A tool path argument such as `../auth/me` is normalised by httpx before the app sees it, so an in-process tool call could reach the routes excluded from the tool list (`/auth/*`, `/devices/*`). | High | `mcp_server._path_segment`: a path argument is one id — no `/ \ ? # %`, not `.`/`..`, percent-encoded — and the final path is re-checked against the excluded prefixes. Tests. |
| R2 | An OAuth connector token is a session row; two browser-only endpoints accepted it as a cookie: `POST /auth/enrollment-tokens` (mint an owner passkey link for 10 minutes after issue) and `POST /auth/refresh` (rotate a connector refresh token into browser cookies, also invalidating the connector). | High | `require_recent_auth` and the auth router's principal helper refuse non-`web` sessions; `refresh_session(kind=…)` refuses a token of the other kind *before* rotating, so a probe cannot revoke the rightful holder. Tests both directions. |
| R3 | Dynamic client registration accepted `javascript:`/`data:` redirect URIs (the SDK types them as `AnyUrl`); `/connect` follows the redirect with `location.assign`. Blocked by the enforcing CSP, but the principle was wrong. | Medium | Registration and approval refuse non-http(s) redirect URIs; the SPA follows only web URLs. Tests. |
| R4 | The consent page named only the client (attacker-chosen under open registration). | Medium | `/connect` now shows the host the code will be sent to and says to cancel if it is unfamiliar. |
| R5 | `client_ip` trusted the *first* `X-Forwarded-For` value (client-supplied), so the login-failure limit was bypassable and forgeable IPs landed in the audit log and the dashboard. | Medium | The last value (the hop Render appends) is used; a global 50-per-15-minute login-failure cap that no forged address can evade. |
| R6 | `delete_cookie` without `Secure` cannot delete a `__Host-` cookie, so logout left dead cookies in production; `/auth/refresh` set cookies before checking the device. | Low | Matching attributes on delete; the refresh decides (and revokes) before it sets cookies; disabled users refused. |
| R7 | The un-prefixed cookie name was honoured over https, weakening `__Host-` pinning. | Low | Only the `__Host-` name counts when cookies are Secure. |
| R8 | Step-up routes did not check the user's role, and several auth mutations (refresh, reauth, logout) skipped the CSRF headers the SPA already sends. | Low | `require_recent_auth` requires an `owner` on a web session and the CSRF headers; refresh/reauth/logout check them too. |
| R9 | A malformed passkey credential id raised a 500 instead of a counted login failure. | Low | Treated as an unknown credential. |
| R10 | uvicorn's own loggers do not propagate to the root, so the secret-redaction filter missed "Exception in ASGI application" lines. | Low | Filter attached to `uvicorn` and `uvicorn.error` handlers. |
| R11 | The enforcing CSP had no `frame-src`, so `default-src 'self'` would have blocked the PDF preview's `blob:` iframe in production — the one place the CSP was tighter than the app. | Functional | `frame-src 'self' blob:`. `vite preview` now serves the production CSP (vite.config.ts reads `_headers`), so the **whole browser suite runs under it** and a dedicated check pins the header and the PDF frame. |

Noted, not changed (low impact or deliberately out of scope): the REPS evidence link URL is not
restricted to the bucket host (Sheets refuses `javascript:` links; the SPA re-reads through
`safeHref`); `/register` and `/authorize` are unauthenticated writers in OAuth mode (rate-limit
later if it ever matters); refresh-replay detection remembers one generation; the Phase 0 app
key in `localStorage` is retired by setting `APP_KEY_MODE=off` once passkeys are enforced; MCP
sessions stay exempt from step-up on `/send-offer` (the device approval is the human in the
loop, and the owner may drop `send_offer` from `MCP_SCOPES`).

**Verification after the fixes.** Backend 525 passed; `verify_regression.py verify` identical;
vitest 87 files / 1383 tests; `npm run build`; Playwright chromium 97 passed / 3 skipped **under
the production CSP** — the same 9 golden failures as before, all from PR #46's calculator
change on `main`, none from this branch.
