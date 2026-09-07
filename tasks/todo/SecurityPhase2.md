# Security Phase 2 — passkeys and sessions

Same branch and PR as Phases 0–1 (`claude/security-phase-0-yxjnsp`, PR #44). Scope:
`SECURITY_PLAN.md` §3.2 (Pillar 1), §3.6 (the MCP connector as a device) and roadmap Phase 2.
Everything ships behind `AUTH_MODE=off` (default) and `DEVICE_POLICY=off` (default): an
un-migrated deployment behaves exactly as before, with no login screen.

## Plan

- [x] **P2.1** (0.5 h) — Dependencies: `webauthn==3.0.0` (py_webauthn) and
      `@simplewebauthn/browser@13`.
- [x] **P2.2** (3.5 h) — Tables `users`, `webauthn_credentials`, `devices`, `sessions`,
      `enrollment_tokens`, `auth_challenges` (`DAL/data_models/auth/models.py`), CRUD
      (`DAL/crud/auth.py`). Created by `create_all`; no migration step needed.
- [x] **P2.3** (3 h) — Settings (`AUTH_*`), the `require_session` dependency (off / shadow /
      enforce, CSRF: `Origin`/`Sec-Fetch-Site` + `X-Requested-With` on unsafe methods),
      `require_recent_auth` for step-up.
- [x] **P2.4** (5 h) — Ceremonies: enrollment links (single use, 15 min), registration
      (`residentKey=required`, `userVerification=required`, attestation `none`, synced-passkey
      flags stored, sign count 0 accepted), login with discoverable credentials, re-auth;
      sessions with a 15-minute access cookie and a 30-day rotating refresh cookie whose replay
      revokes the family; device rows (`DEVICE_POLICY`), HttpOnly `Lax` cookies (`__Host-` over
      https), login-failure rate limit through the audit table.
- [x] **P2.5** (2 h) — `routers/auth.py` (`/auth/config`, register, login, refresh, me, logout,
      reauth, enrollment-tokens); `main.py` attaches `require_session` next to the Phase 0 key on
      every router except `health` and `auth`.
- [x] **P2.6** (1 h) — `manage.py`: `enroll`, `list-devices`, `approve-device`, `revoke-device`,
      `revoke-sessions`.
- [x] **P2.7** (1 d) — MCP: the connector is a `service` user with one trusted `mcp` device and a
      process-local session; in-process tool calls carry its cookie so the same gate applies;
      a revoked connector device stops every tool and is never silently re-created;
      `/auth/*`, `/devices/*`, `/sessions/*`, `/credentials/*` never become tools.
- [x] **P2.8** (4 h) — Frontend: `api/auth.ts`, `stores/authStore.ts`, `/login`, `/enroll`,
      `/pending` views, router guard (a no-op while the API says `auth_mode=off`),
      `withCredentials`, `X-Requested-With`, 401 → one silent refresh → `/login`; Vite `/api`
      proxy; Netlify `/api/*` rewrite (used once `VITE_API_URL=/api` is set).
- [x] **P2.9** (2.5 h) — Tests: a software passkey (`tests/webauthn_helpers.py`),
      `test_auth_passkeys.py` (24 cases), `authStore.test.ts` (9), Playwright
      `checks/auth.spec.ts` on chromium's virtual authenticator (enrol via `manage.py`, sign
      out, sign in with the discoverable credential, reload; a used link is refused).
- [x] **P2.10** (2 d) — MCP OAuth 2.1 + PKCE through `mcp.server.auth` (`BL/auth/oauth.py`,
      `MCP_AUTH_MODE=oauth`): dynamic client registration, `/authorize` parks the request and
      sends the browser to the SPA's `/connect`, a trusted owner approves (step-up), the code
      is exchanged for a bearer token that *is* an `mcp` device session; refresh rotates,
      `/revoke` and `revoke-device` end it; tool calls run as the approving owner. `path` mode
      (the secret URL) stays the default.
- [x] **P2.11** (0.5 h) — Snapshots re-recorded (auth routes and tables); README "Passkeys"
      section and env rows; this file.

## Tests

- Backend: `pytest` — the whole suite plus `test_auth_passkeys.py` and `test_mcp_oauth.py`
  (8 cases: metadata documents, 401 with a `WWW-Authenticate` hint, consent needs a trusted
  session, approve → tools as the owner with `AUTH_MODE=enforce`, refresh rotation and replay,
  `/revoke`, device revocation, single-use code bound to its verifier, path mode unchanged);
  `verify_regression.py verify` identical after the deliberate re-record (`openapi`: the
  `/auth/*` operations; `schema`: the eight tables). `calculations`, `models`, `endpoints`
  unchanged.
- Frontend: `npm test` (87 files), `npm run build` (vue-tsc), Playwright chromium with the
  passkey spec.
- Static: `pyflakes` on the new modules.

## MCP server

New endpoints `/auth/*` are **excluded** from tool generation on purpose. The connector itself
authenticates as a device whose session goes through `require_session` like the browser's:
under the path secret it is the shared `mcp-connector` device; under `MCP_AUTH_MODE=oauth`
each connector is its own `mcp` device, approved on `/connect` by a signed-in owner and
running every tool as that owner (audited with the user id). Revoking the device
(`manage.py revoke-device`, or the dashboard in Phase 3) stops every tool.

## Security (`.claude/security.md`)

- [x] No secret in any file; session, refresh, enrollment and device tokens are stored as
      SHA-256 hashes; the raw values exist only in HttpOnly cookies (never readable by JS) and
      in the enrollment link the owner is shown once.
- [x] WebAuthn: origin and RP id pinned, user verification required, challenges single use and
      5-minute, attestation not trusted (`none`), synced passkeys (sign count 0) accepted while
      a decreasing counter on a hardware key is rejected by py_webauthn.
- [x] Refresh replay revokes the family; a revoked device kills its sessions; the login and
      enrollment failure paths are rate limited and audited.
- [x] Every new flag defaults to today's behaviour.

## Review

**What changed.** Passkey sign-in, server-side sessions and the connector-as-device model,
all additive and all behind flags whose defaults keep today's behaviour. `main.py` attaches
`require_session()` (with the Phase 0 key) to every router except `health` and `auth`; the
dependency reads cookies from the raw request, so no existing operation's OpenAPI changed.
New: `DAL/data_models/auth/models.py` (8 tables), `DAL/crud/auth.py`, `BL/auth/*` (settings,
session, device, register, login, service, oauth, session_dependency), `routers/auth.py`
(12 operations incl. the two `/auth/oauth/*` consent calls), `manage.py`, the SPA's auth
store and the `/login`, `/enroll`, `/pending`, `/connect` views, the Vite `/api` proxy and the
Netlify `/api/*` rewrite.

**Functional invariants held.** Backend 418 passed (was 386 after Phase 1; +24 passkey, +8
OAuth); `verify_regression.py verify` identical after the one deliberate re-record;
vitest 87 files / 1379 tests; `npm run build`; Playwright chromium 103 passed / 3 skipped
including `checks/auth.spec.ts` (enrol → sign out → sign in → reload on the virtual
authenticator) — see the e2e note below; `verify:ui --fast`: G6 (`npm test` + `npm run build`) green, while G1/G2/G8/GOLDEN-POLICY compare against the UI-overhaul `ui-baseline` tag and fail on `main` identically (absolute paths in `.github/scripts/nightly/*`, backend files changed since that tag) — not gates for this branch.

**Two test-harness adjustments, deliberate.** (1) The network recorder ignores `/auth/*`:
the SPA now asks `/auth/config` and `/auth/me` once on boot, and the feature goldens
describe what a feature asks the API for, not session plumbing — every golden file is
byte-identical. (2) `/login` no longer bounces to the dashboard when the API is not
enforcing sessions and there is no session, so an owner can try a passkey before flipping
`AUTH_MODE`; with a session it still redirects.

**Rollout order** (README "Passkeys"): enrol both owners → `AUTH_MODE=shadow` → watch for
"auth shadow: would reject" → `AUTH_MODE=enforce` → `VITE_API_URL=/api` on Netlify → later,
`MCP_AUTH_MODE=oauth` and re-add the connector with OAuth. Rollback of every step is the env
flip back; nothing is removed.

**Known limits.** The MCP SDK's `/revoke` request model requires `client_secret` even for
public clients (send it empty). `DEVICE_POLICY` approval UI and the devices dashboard are
Phase 3; until then `manage.py approve-device` is the approval path.
