# Security Phase 0 — stop the bleeding

Branch: `claude/security-phase-0-yxjnsp` (cut from the tip of `main`, `38ba79d`). Scope and rationale:
`SECURITY_PLAN.md` §4, Phase 0. No architecture change, no feature change; every gate ships
behind an env flag that defaults to today's behaviour.

## Plan

- [ ] **P0.1** (30 min, owner) — Inventory the live Render / Netlify env vars and the bucket IAM
      (`MCP_PATH_SECRET`, `REPS_LINK_STYLE`, `EMAIL_PASSWORD`, `MERCURY_API_TOKEN_*`). Not
      reachable from this session; listed for the owner in the Review.
- [x] **P0.2** (2 h) — Shared-key gate. `BackEnd/BL/auth/common/app_key.py` with
      `require_app_key` (`APP_KEY_MODE=off|shadow|enforce`, default `off`; `APP_KEY`); attached
      in `main.py` to every router except `health`. Frontend: `X-App-Key` request header from
      `localStorage['bw.appKey']`, a one-time key prompt when the API answers 401
      `app_key_required`.
- [x] **P0.3** (15 min) — Delete the Gmail app-password prefix/length logging
      (`offer_email.py:26-30`). Rotation of `EMAIL_PASSWORD` is the owner's step.
- [ ] **P0.4** (45 min, owner) — Recreate the Mercury tokens as Read Only with the Render IP
      allow-list; rotate them into Render. Runbook in `SECURITY_PLAN.md` §6.
- [x] **P0.5** (1 h) — REPS objects: 16-hex random suffix in object names; `make_public()` per
      object only when `REPS_OBJECT_ACL_PUBLIC=true` (default `true`, unchanged) so the owner can
      switch the bucket to `allUsers: legacyObjectReader` first and then drop the per-object ACL;
      docstring corrected (`public` is the default).
- [x] **P0.6** (15 min) — `/docs`, `/redoc`, `/openapi.json` off when `APP_ENV=production`
      (`APP_ENV` defaults to `production` on Render, `development` elsewhere).
- [x] **P0.7** (1.5 h) — `frontend/public/_headers` (CSP report-only, HSTS, nosniff, referrer,
      permissions, `frame-ancestors 'none'`), `frontend/public/_redirects` (the SPA rule),
      the pre-paint script moved to `frontend/public/theme-init.js`; `theme.test.ts` follows.
- [x] **P0.8** (1.5 h) — `SendOfferReq`: `EmailStr`, `max_length`, CR/LF rejected; the e-mail
      body HTML-escapes the interpolated fields. Sheet append: free-text cells that start with
      `= + - @` get a `'` prefix (still `USER_ENTERED`, so numbers, booleans and dates behave
      exactly as before).
- [x] **P0.9** (1.5 h) — `safeHref()` at the twelve `:href` sites plus `rel="noopener noreferrer"`.
- [x] **P0.10** (1.5 h) — MCP fail-closed: `mount()` refuses to start in production without
      `MCP_PATH_SECRET`, warns under 32 characters; uvicorn access log redacts `/mcp/<secret>`.
- [x] **P0.11** (15 min) — `call_tool` passes `X-App-Key` on the in-process request so the
      45 tools keep working when the gate is on.
- [x] **P0.12** (1 h) — Tests (below), snapshots, docs, review.

## Tests

- `BackEnd/tests/test_auth_gate.py` — every operation in the OpenAPI snapshot returns 401
  without the key under `enforce`, passes with it, passes without it under `off` and `shadow`;
  `/helloworld` stays public.
- `BackEnd/tests/test_email_hardening.py` — `agent_email` must be an e-mail; CR/LF rejected;
  HTML in `agent_name` is escaped in the body; the logs no longer carry the password prefix.
- `BackEnd/tests/test_sheet_values.py` — `neutralize_formula()` on `=`, `+`, `-`, `@`, and
  plain text; the appended row keeps `total_hours` numeric and the boolean cell as before.
- `BackEnd/tests/test_mcp_mount.py` — production without a secret refuses to mount; development
  mounts at `/mcp`; the access-log filter redacts the secret; `call_tool` sends the app key.
- `frontend/src/utils/safeHref.test.ts` — `https://`, `http://` pass; `javascript:`, `data:`,
  bare hosts and empty values yield `undefined`.
- `frontend/src/design/theme.test.ts` — reads `public/theme-init.js` instead of `index.html`.
- Existing suites: `pytest` (incl. the 88 MCP tests), `verify_regression.py verify`,
  `npm test`, `npm run build`, `npm run verify:ui -- --fast`.

## MCP server

No endpoint is added. The app-key gate is honoured by the in-process tool calls (P0.11), so the
tool list and behaviour of all 45 tools are unchanged; `MCP_PATH_SECRET` becomes mandatory in
production (P0.10).

## Security (`.claude/security.md`)

- [x] No secret value in any file; the frontend bundle holds no key (the key is typed by the
      user and kept in that browser's `localStorage` only).
- [x] Every new input path validated; every new env flag defaults to today's behaviour.

## Review

**Changed**

Backend
- `BackEnd/BL/auth/common/app_key.py` (new) — `require_app_key`: `APP_KEY_MODE=off|shadow|enforce`
  (default `off`), `APP_KEY`, constant-time compare, `X-App-Key` header read from the raw request
  so the OpenAPI contract does not change.
- `BackEnd/BL/common/logging_redact.py` (new) — `MCPPathRedactFilter` on `uvicorn.access`:
  `/mcp/<secret>` is logged as `/mcp/[redacted]`.
- `BackEnd/main.py` — `APP_ENV` (defaults to `production` on Render via `RENDER=true`, else
  `development`); no `/docs`, `/redoc`, `/openapi.json` in production; the gate attached to every
  router except `health` at `include_router` time; the log filter installed.
- `BackEnd/mcp_server.py` — `check_secret_policy()`: refuses to mount an unprotected `/mcp` in
  production, warns under 32 characters; in-process tool calls send `X-App-Key`.
- `BackEnd/BL/email/common/offer_email.py` — the five password-logging lines removed; `agent_name`
  and `property_address` HTML-escaped before interpolation (visually identical for real values).
- `BackEnd/ReqRes/common/send_offer_schemas.py` — `EmailStr`, `min/max_length`, CR/LF rejected on
  header-bound fields, `inspection_period_days` 0–365. `email-validator` added to
  `requirements.txt`.
- `BackEnd/BL/reps/common/reps_service.py` — `neutralize_formula()` + `build_log_row()` (row
  building extracted, unchanged order and types; free-text cells starting with `= + - @` get a
  leading `'`); 16-hex `secrets.token_hex(8)` suffix in both object-name builders; per-object
  `make_public()` gated by `REPS_OBJECT_ACL_PUBLIC` (default `true`); docstring says `public` is
  the default.
- `BackEnd/tests/_regression_snapshots/{openapi,models}.json` — re-recorded deliberately: the
  only diff is the `SendOfferReq` constraints (`format: email`, `maxLength`, `minLength`,
  `minimum`/`maximum`). `calculations` and `endpoints` snapshots are byte-identical.

Frontend
- `frontend/src/utils/safeHref.ts` (+ test) — `https?:` only; used at the thirteen `:href` sites
  in `MyDeals.vue`, `BoughtDeals.vue`, `RepsEntriesList.vue`, `RepsEntryModal.vue`, each of which
  also gained `rel="noopener noreferrer"`. (`RepsEntryModal`'s map link was already safe; wrapped
  for uniformity.)
- `frontend/src/auth/appKey.ts`, `frontend/src/components/shell/AppKeyGate.vue`, `App.vue`,
  `api/index.ts` — the key prompt (shown only after a 401 `app_key_required`), `localStorage`
  storage, request header, 401 interceptor.
- `frontend/public/theme-init.js` + `index.html` — the pre-paint script is external so the CSP can
  say `script-src 'self'`; `theme.test.ts` reads the new file.
- `frontend/public/_headers`, `frontend/public/_redirects` — HSTS, nosniff, `X-Frame-Options`,
  referrer and permissions policies, a **report-only** CSP; the SPA fallback rule.
- `README.md` — env table rows for `APP_ENV`, `APP_KEY_MODE`/`APP_KEY`, `REPS_OBJECT_ACL_PUBLIC`,
  `MCP_PATH_SECRET` now required in production; deploy row mentions `_headers`/`_redirects`.

**Verified locally** (PostgreSQL 16 from the system binaries on 127.0.0.1:55432; Docker daemon
unavailable here)
- New backend tests: `test_auth_gate.py` (every operation in the OpenAPI snapshot: 401 without
  the key, never 401 with it; `/helloworld` public; off/shadow never reject),
  `test_email_hardening.py`, `test_sheet_values.py`, `test_mcp_mount.py` — all green.
- Full backend suite (existing 206 + new): green, exit code 0; `verify_regression.py verify`:
  all snapshots identical after the deliberate re-record.
- Frontend: `npm test` 86 files / 1370 tests green; `npm run build` (vue-tsc + vite) green;
  `dist/` contains `_headers`, `_redirects`, `theme-init.js`.
- `npm run verify:ui -- --fast`: G6 PASS, G-HOVER PASS; G1/G2 report only "baseline tag
  ui-baseline is missing" (this clone has no tags; identical on `main`); G8's five FAIL lines are
  the pre-existing runner-home paths in `.github/scripts/nightly/*` (none in this change);
  G3/G4 are advisory.
- Playwright chromium project against the real backend: see the line below the table in the
  next section.

**Behaviour unchanged, by construction**: every new flag defaults to today's behaviour
(`APP_KEY_MODE=off`, `REPS_OBJECT_ACL_PUBLIC=true`, CSP report-only, `APP_ENV=development`
outside Render). The only observable changes in production are: no interactive docs, the Gmail
password prefix no longer in logs, `send-offer` rejecting malformed e-mail addresses with 422,
and REPS free-text cells starting with `= + - @` gaining an invisible leading apostrophe.

**For the owner (dashboard steps, not code)**
1. P0.1 — inventory the live env vars; confirm `MCP_PATH_SECRET` is 32+ characters (rotate if
   not) and note that the app now refuses to boot on Render without it.
2. P0.3 — rotate `EMAIL_PASSWORD` (its first two characters have been in the logs until now).
3. P0.4 — recreate the Mercury tokens as Read Only with the Render outbound IPs allow-listed
   (`SECURITY_PLAN.md` §6 runbook) and rotate them into Render.
4. P0.5 — on the evidence bucket, change `allUsers` from `objectViewer` to
   `legacyObjectReader` (get, no list), then set `REPS_OBJECT_ACL_PUBLIC=false`.
5. P0.2 — when ready to close the API: generate a 32+ character `APP_KEY`, set
   `APP_KEY_MODE=shadow` for a day or two, watch the logs for "would reject", then
   `APP_KEY_MODE=enforce`. The site will ask each of you for the key once per browser; the
   claude.ai connector keeps working because tool calls carry the key.
6. Netlify: after the first deploy, check the browser console for CSP report-only violations
   before Phase 3 enforces the policy.
