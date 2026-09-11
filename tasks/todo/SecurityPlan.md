# Security audit and execution plan (`SECURITY_PLAN.md`)

Branch: `claude/security-audit-plan-yxjnsp` (cut from the tip of `main`, `99d7d0b`, after the MCP server merged).

## Goal

Audit the entire repository as a Principal Security Architect using the Trail of Bits skills and
methodologies, and produce `SECURITY_PLAN.md`: threat model, CVSS-ranked vulnerability matrix with
`file:line` evidence, the target architecture for passkeys / secrets / device allowlisting / the MCP
server, and a phased roadmap with tests and rollback per step. **Documentation only; no
implementation code.** Hard constraint from the owner: every feature keeps working after every phase.

## Plan

- [x] **S1** (10 min) — Clone `trailofbits/skills` into the session scratchpad (not the repo) and read
      `insecure-defaults`, `sharp-edges`, `entry-point-analyzer`, `vulnerability-triage-brocards`,
      `supply-chain-risk-auditor`, `static-analysis`.
- [x] **S2** (45 min) — Read the core files directly: `BackEnd/main.py`, `db.py`, `bootstrap.py`,
      every router, the Mercury client, the REPS service and schemas, the e-mail composer,
      `requirements.txt`, `tests/conftest.py`, the frontend API client, router, `index.html`,
      `vite.config.ts`, `package.json`, both workflows, `serve_throwaway.py`, the README deployment
      section; sweep git history for secrets.
- [x] **S3** (25 min) — Three parallel read-only sweeps (backend routers + DAL; frontend + CI + deploy;
      integrations + secrets) with `file:line` evidence; spot-verify the headline claims.
- [x] **S4** (15 min) — Architecture design pass (passkeys, sessions, secrets, devices) and reconcile
      it with the owner's decisions (stay on `netlify.app`, Apple sign-in as recovery only, Mercury
      Phase 1 controls without a broker).
- [x] **S5** (20 min) — Re-audit the delta on `main` (MCP server, CI job, CLAUDE.md rules 6) and fold
      it in: F-22 … F-28, pillar §3.6, roadmap items 0.10, 0.11, 1.7, 2.11, 2.12.
- [x] **S6** (40 min) — Write `SECURITY_PLAN.md`.
- [x] **S7** (10 min) — Write this file.
- [x] **S8** (10 min) — Verify (see Tests) and commit; push; open the PR.

## Tests

A document carries no behaviour, so there are no unit, integration or E2E tests to add. The gates
that apply:

- Gate G8 (no absolute filesystem path in any tracked file): `node frontend/scripts/audit/paths.mjs`,
  or the same regexes applied by hand when `frontend/node_modules` is not installed.
- Every `file:line` cited in the vulnerability matrix re-checked with `grep -n` against the tree at
  `99d7d0b` (the MCP-server line numbers were verified against `origin/main` before writing).
- Every Mermaid block parses (six blocks; checked with mermaid in headless Chromium).
- Every relative link and every referenced path in the document exists in the tree.
- `git status` shows only the two new files; nothing under `BackEnd/`, `frontend/` or `.github/`
  changed.

## MCP server

No endpoint is added by this task. The plan itself records, per future endpoint it introduces
(`/auth/*`, `/devices/*`, `/sessions/*`, `/credentials/*`): these are **deliberately excluded** from
MCP tool generation (an LLM must not enroll passkeys or approve devices); `GET /devices` and
`POST /devices/{id}/revoke` may be added later as explicit, annotated admin tools. The connector
itself becomes a trusted *device* with its own session (`SECURITY_PLAN.md` §3.6), so all 45
existing tools keep working through the authentication gate.

## Security (CLAUDE.md rule 6, from `.claude/security.md`)

- [x] The two new files contain no secret values: no tokens, passwords, private keys, Google Sheet
      ids, Mercury account ids or Render service ids. Grep for the credential-shaped patterns
      (`BEGIN PRIVATE KEY`, `AIza`, `sk_live`, `ghp_`, `secret-`, 32+ hex runs) returns nothing.
- [x] The only hostnames and identifiers named are ones already public in `README.md` and
      `REPS_README.md` (`bigwhales.netlify.app`, `BigWhalesLLC@gmail.com`, the Render host is
      referred to as `<render-host>`).
- [x] No frontend file changed, so nothing sensitive can have reached the bundle.
- [x] The findings that name exploitable behaviour (`=IMPORTXML`, `javascript:` URLs) are described,
      not provided as working payloads against the live site.

## Review

**Changed**

- `SECURITY_PLAN.md` — new, the deliverable: executive summary; the zero-regression invariant with
  a feature-by-feature table and the method that guarantees it; the decisions taken with the owner;
  threat model (ten assets, seven actors, a Mermaid attack graph); a 28-finding vulnerability matrix
  with CVSS 3.1 vectors, `file:line` locations, root causes and feature-preserving remediations, plus
  a "confirmed not vulnerable" table; the target architecture in four pillars (passkeys + sessions,
  Mercury secrets, trusted devices, the MCP server as a device) with five Mermaid sequence diagrams
  and full data models; a four-phase roadmap (0 / 1 / 2 / 3) with per-step files, estimates, tests
  and rollback flags; verification, shadow-mode exit criteria and a feature inventory checklist;
  runbooks; appendices for the deferred broker / Secret-Manager / envelope-encryption designs, the
  Trail of Bits skills used, and the environment variables the roadmap introduces.
- `tasks/todo/SecurityPlan.md` — this file.

**What the audit found, in one line each**

- Critical: no authentication on any of the 45 routes (F-01); the REPS identity is a client string
  (F-03); the MCP server's in-process tool calls would break under a naive auth rollout (F-23).
- High: open e-mail relay with HTML injection (F-02); world-readable evidence bucket with anonymous
  unbounded uploads (F-04); bank balances anonymous (F-05); Sheets formula injection (F-06); no
  limits anywhere (F-08); MCP secret in the URL, fail-open, logged (F-22); MCP confused-deputy
  surface (F-24).
- Medium / Low: twelve `javascript:`-capable `:href` sites (F-07); exception text to clients
  (F-09, F-25); no security headers (F-11); information disclosure (F-12); over-scoped service
  account (F-13); CORS wildcard with credentials (F-14); ReportLab markup (F-15); floating
  dependencies and tag-pinned actions (F-16, F-28); destructive DDL at import (F-17); deploy config
  outside version control (F-18); production console logging and GPS in `localStorage` (F-19);
  numeric bounds on the wrong layer (F-20); the Gmail password prefix in logs (F-10, one line).
- Clean: SQL, command and deserialization injection; PDF SSRF; upload traversal; CI script
  injection; secrets in git history and in the bundle; open redirects; Mercury token handling.

**Verified**

- Every `file:line` in the matrix resolves on `99d7d0b` (re-checked with `grep -n`; the
  `main.py` router loop moved to `:37-38` after the MCP merge and the matrix says so).
- All six Mermaid blocks parse with mermaid 11 (`flowchart-v2` ×1, `sequence` ×5). A first pass
  failed on four sequence diagrams because `;` inside a message is a Mermaid statement separator;
  they were rewritten with commas.
- Gate G8 (`node frontend/scripts/audit/paths.mjs`, after `npm ci`): the two new files contain no
  absolute path. The gate reports 5 FAILs and 3 WARNs, all pre-existing on `main` in
  `.github/scripts/nightly/make_preview_fixtures.py` and `.github/scripts/nightly/tests/test_nightly.py`
  (they hard-code the GitHub runner's home path); identical count on `origin/main` with this
  branch's files stashed. Not touched here; noted for the owner.
- No secret-shaped string in either file (the only regex hit is the sentence in this file that
  lists the patterns).
- `git status` shows only the two new files.

**Not done / for the owner**

- Live Render and Netlify configuration could not be read from this session (the Render MCP needs a
  workspace selection); Phase 0 step 0.1 is that inventory.
- Open defaults to confirm: O-5 session lifetimes, O-6 keep public evidence links, O-7 both users
  approve devices, O-8 all 45 tools on the connector by default.
