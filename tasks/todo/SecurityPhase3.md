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
