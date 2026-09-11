# Security Phase 1 — secrets and critical fixes

Same branch and PR as Phase 0 (`claude/security-phase-0-yxjnsp`, PR #44), one commit per phase.
Scope: `SECURITY_PLAN.md` §4, Phase 1 (findings F-05, F-08, F-09, F-12, F-13, F-16, F-17, F-18,
F-21, F-24, F-25, F-26, F-28). No feature change; every new flag defaults to today's behaviour.

## Plan

- [x] **P1.1** (3 h) — `BL/common/secret.py` (`Secret`), Mercury client: tokens as `Secret`,
      only `/accounts` ever requested (pinned by a test), upstream error bodies not relayed,
      60 s cache (`MERCURY_CACHE_SECONDS`), a `mercury_fetch` audit row per call.
- [x] **P1.2** (1 d) — Global exception handler (`internal error` + `ref`), no `str(exc)` in any
      router detail, fixed SMTP error strings, no recipient/agent PII in logs; `/reps/config-status`
      without bucket/prefix, `/reps/log` masks the sheet id, the 400 no longer lists the user ids,
      the worksheet error no longer lists tab names or the sheet id.
- [x] **P1.3** (1 d) — `BodyLimitMiddleware` (`MAX_BODY_BYTES`, 30 MB), upload caps (10 files,
      25 MB each and in total) enforced before buffering, magic-byte check, stored Content-Type
      from the allow-listed extension, `max_length` on every deal string / comps / REPS lists /
      substage dict, `audit_log` table + `send_offer` rate limit (`SEND_OFFER_PER_HOUR`, 30).
- [x] **P1.4** (2 h) — Service-account scopes: `cloud-platform` dropped; `devstorage.full_control`
      only while `REPS_OBJECT_ACL_PUBLIC=true`, else `read_write`. (Bucket-level IAM narrowing
      and key rotation are owner steps.)
- [x] **P1.5** (0.5 d) — `sslmode=require` for PostgreSQL in production; `BackEnd/.env.example`,
      `frontend/.env.example`. The destructive-migration gate, `render.yaml` and `netlify.toml`
      are deliberately not added (see Review).
- [x] **P1.6** (1 d) — `requirements.txt` pinned exactly; FastAPI 0.115.5 → 0.141.1 (Starlette
      1.6.0, clears eight Starlette advisories); `npm audit fix` (lockfile only, 0 advisories
      left); `.github/dependabot.yml`; a **Security checks** CI job (`pip-audit`, Bandit at
      medium/medium, `npm audit --omit=dev --audit-level=high`, Gitleaks); the two tracked `.pyc`
      files untracked.
- [x] **P1.7** (1 d) — MCP: `ToolAnnotations` per tool (read-only / destructive / open-world),
      `MCP_SCOPES` allow-list (default all), an `mcp_tool_call` audit row per call, the tool
      builder walks FastAPI's nested routers, upload fields detected by `contentMediaType`.
- [x] **P1.8** (30 min) — Snapshots re-recorded; README env rows; this file.

## Tests

- New: `test_secret.py`, `test_error_handler.py`, `test_limits.py` (body limit, field caps,
  upload caps, no user enumeration), `test_mercury_client.py` (only `/accounts`, header only,
  cache, generic errors, errors never cached), `test_mcp_annotations.py` (annotations, scopes,
  audit row), `test_audit.py` (record/count, send-offer 429, secret-value log filter).
- Existing suites: `pytest` (386 passed), `verify_regression.py verify` (identical after the
  deliberate re-record), `npm test` (1370), `npm run build`, `verify:ui --fast`, Playwright
  chromium against the real backend (result recorded in the Review).
- Static: `pip-audit -r requirements.txt` clean, `bandit -ll -ii` clean, `npm audit --omit=dev`
  clean.

## MCP server

No endpoint added. Tool behaviour is unchanged by default; each tool now carries annotations,
`MCP_SCOPES` can narrow the set, and every call is audited.

## Security (`.claude/security.md`)

- [x] No secret value in any file; `.env.example` files hold empty values only.
- [x] Every new input path validated (`max_length`, upload caps, magic bytes, body limit).
- [x] Every new flag defaults to today's behaviour.

## Review

**Changed** — see the commit; the notable decisions:

- **FastAPI 0.141.1.** `app.routes` now nests included routers (`_IncludedRouter`) instead of
  flattening them, so `mcp_server._build_tools` walks `original_router.routes`; Starlette 1.x
  describes upload fields with `contentMediaType` rather than `format: binary`, so `_is_binary`
  accepts both. Everything else passed untouched. The OpenAPI snapshot picked up Starlette's
  `ValidationError.ctx/input` properties along with the new length caps.
- **Error texts the UI asserts are unchanged**: `No Mercury tokens found…` (503) and
  `Failed to send email: Email password not configured` (500) are deliberate configuration
  messages, not exception text, and the e2e specs check them. Only exception text and the
  driver's raw `IntegrityError` went away.
- **Sheet cell hygiene stays on `USER_ENTERED`** (Phase 0) so typed cells are unchanged.
- **Not done, on purpose.** (1) A `MIGRATIONS_ALLOW_DESTRUCTIVE` gate: skipping the `DROP
  COLUMN` steps could leave a NOT NULL legacy column in place and break inserts on a database
  that has not been migrated yet, which is a worse failure than the one it prevents; the
  existing isolation guard already protects every test and e2e run. (2) `render.yaml` /
  `netlify.toml`: both services are configured in their dashboards and a Blueprint or
  `netlify.toml` that does not match them exactly would change the deploy; documented instead.
  (3) SHA-pinning the GitHub Actions: Dependabot's `github-actions` ecosystem will propose the
  pins; the SHAs were not looked up from this session. (4) Semgrep in CI: left for Phase 3.
  (5) F-20 (numeric bounds on persistence): deferred to Phase 3; the global handler now turns
  the `NumericValueOutOfRange` 500 into `internal error` + ref instead of a raw driver message.

**Verified locally** (PostgreSQL 16 on 127.0.0.1:55432)
- `pytest`: 386 passed, 0 failed (the 88 MCP tests included; six new test files).
- `verify_regression.py verify`: all five snapshots identical after the deliberate re-record
  (`schema`/`models`: the `audit_log` table; `openapi`/`models`: the length caps and Starlette's
  `ValidationError.ctx/input`; `endpoints`: three error strings). `calculations` unchanged.
- `npm test`: 86 files / 1370 tests; `npm run build` green against the audited lockfile.
- `verify:ui --fast`: G6 and G-HOVER pass; G1/G2 report only the missing `ui-baseline` tag; G8's
  five findings are the pre-existing runner paths in `.github/scripts/nightly/*`.
- Playwright chromium against the real backend: 101 passed, 3 skipped (allow-listed), 0 failed.
  (A first attempt ran concurrently with `verify:ui`, whose G6 step rebuilt `dist/` under the
  preview server and made the page call the wrong port; re-run alone it is green. Do not run
  the two together.)
- `pip-audit -r requirements.txt`: no known vulnerabilities; `bandit -ll -ii`: clean;
  `npm audit --omit=dev`: 0 vulnerabilities; `pyflakes` on the changed files: clean.

**For the owner (dashboard steps)**
1. Bucket IAM: bind `roles/storage.objectAdmin` on the evidence bucket only (not the project);
   rotate the service-account key; after switching `allUsers` to `legacyObjectReader`, set
   `REPS_OBJECT_ACL_PUBLIC=false` (the app then asks for the narrower `read_write` scope).
2. Render: nothing to set for Phase 1 — `sslmode=require` is added automatically when the
   `DATABASE_URL` has no `sslmode`; if the Render Postgres URL already carries one it is kept.
3. GitHub: enable Dependabot alerts/security updates in the repo settings so the weekly PRs run.
