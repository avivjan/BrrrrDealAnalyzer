# Fold the "MCP server tests" CI job into "Backend tests"

Goal: one `pytest` in the Backend job discovers every `BackEnd/tests/test_*.py`, MCP files
included, so a new MCP test file never needs a `ci.yml` edit. Branch
`ci/fold-mcp-tests-into-backend` from `main` (99d7d0b, PR #37 merged).

**Job diff, before touching anything.** The MCP job and the Backend job use the same
`postgres:16` service, the same Python setup and cache, the same `TEST_DATABASE_URL`, the
same 15-minute timeout and the same working directory. The Backend job additionally runs
the migration smoke, coverage and the nightly package's unit tests. The MCP job had
nothing the Backend job lacks, so folding it in drops no requirement. The Backend job's
plain `pytest` already runs all three `test_mcp*.py` files today (206 tests = 118 original
+ 88 MCP); the MCP job was a duplicate run with its own check name and JUnit artifact.

- [x] **S1** (5 min) — Branch + this plan.
- [x] **S2** (10 min) — `ci.yml`: delete the `mcp` job and the `mcp_result` workflow output; the Backend job's `pytest` stays directory-wide (no file list); rewrite the comments that described the two jobs.
- [x] **S3** (20 min) — Nightly. `e2e-nightly.yml`: drop the `junit-mcp` download, `MCP_OUTCOME` and `--mcp-junit`. Email package: keep the "MCP server" column, now **derived from the backend JUnit by test-module prefix** (`tests.test_mcp*`) via a small `junit.subset()` helper; drop the separate MCP jobs line (there is no job); fixtures put the MCP cases inside `backend-junit.xml`; unit tests updated (subset math, column still rendered, no `--mcp-junit` flag).
- [x] **S4** (10 min) — README: CI paragraph and Contributing back to two checks, testing-table MCP row points at plain `pytest`, known-gaps wording; `ci.yml` / `e2e-nightly.yml` comments.
- [x] **S5** (10 min) — Verify: full `cd BackEnd && pytest` still 206 passed on the local Postgres; nightly package unit tests; both workflows validated against the GitHub workflow schema; `verify_regression.py verify` (no app change, sanity).
- [x] **S6** (5 min) — Security task (`.claude/security.md`): re-read the diff (workflows, email package, docs) for secrets, tokens or sensitive paths; nothing here touches the frontend or the app.
- [ ] **S7** (5 min) — Commit, push, open the PR; report which checks run and the manual ruleset step.

**Branch protection.** The GitHub tools in this session cannot read or edit branch rules or
rulesets, so this is a manual check on the owner's side: under *Settings → Branches* (or
*Rules → Rulesets*), if "MCP server tests" is listed as a required status check it must be
removed, otherwise every future PR waits forever for a check that never reports. The
README's known-gaps note says no checks are required yet; verify rather than assume.

## Review

**What changed.** `ci.yml` loses the `mcp` job and the `mcp_result` output (62 lines gone);
the Backend job's plain `pytest` was already directory-wide and is unchanged apart from a
comment saying the MCP files ride along. `e2e-nightly.yml` loses the MCP artifact download,
`MCP_OUTCOME` and `--mcp-junit`. In the email package, `junit.subset()` (new, ~25 lines)
filters a parsed suite by module prefix; `main.py` builds the MCP column from the backend
JUnit with it and no longer lists a separate MCP job; the preview fixture writes the MCP
cases into `backend-junit.xml`; the HTML column subtitle says "tests/test_mcp*, from the
backend run". README: two checks again, MCP row points at plain `pytest`, prove-a-change
and known-gaps wording.

**Nightly email approach (step 3): derived column.** The parser keeps every case's module
name, so the "MCP server" column is computed from the single backend JUnit by the prefix
`tests.test_mcp`. Any future `test_mcp_*.py` is included by construction, there is no
second artifact or job outcome to keep in sync, and the column, its failing list and its
slowest list look exactly as before. The jobs block no longer shows an MCP job because there
is none; the verdict is unaffected since the MCP cases fail the Backend job.

**Job reconciliation (step 2).** Diffed before editing: identical Postgres service, Python
setup, `TEST_DATABASE_URL`, timeout and working directory; the MCP job had no requirement
the Backend job lacked. Nothing dropped.

**Branch protection (step 4).** Cannot be read or changed with the tools in this session.
Manual check for the owner: *Settings → Branches* (or *Rules → Rulesets*) on `main`; if
"MCP server tests" is a required status check, remove it, or every PR will wait on a check
that never reports again. The README's known gaps still say no checks are required yet.

**Verified.** `cd BackEnd && pytest` on a local PostgreSQL 16: 206 passed, 0 failed, of
which 88 are `tests/test_mcp*` cases (the 206 already contained the 88 before this change;
"206 + 88" would double count). Nightly package unit tests: 23 OK (the MCP-artifact test is
replaced by a `subset()` unit test and a derived-column assertion). Both workflows validate
against the GitHub workflow JSON schema.

**Security task (S6).** The diff touches workflows, the email package, fixtures, tests and
docs only; no application or frontend code. No secrets, tokens or credentials are added;
the only URLs are a fixture placeholder and the existing docs links.
