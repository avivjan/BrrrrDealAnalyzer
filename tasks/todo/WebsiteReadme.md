# Website README rewrite

Branch: `claude/website-readme-docs-jdffsm` (cut from the tip of `main`, `d677730`).

## Goal

Replace the root `README.md` with a README that is the front door of the repo for
two audiences at once: a person opening the GitHub page (what is this, does it
look good, how do I run it) and an AI agent dropped into the checkout (where is
what, which rules must not be broken, how do I prove a change). Keep everything
the old README said that is still true; move the long checklists under
collapsible sections so the page stays scannable.

## Plan

- [x] **Survey** (15 min) — read the existing root, backend and frontend READMEs,
      `main.py`, `db.py`, the routers, the frontend router, CI workflows, gates
      G1/G8, and the v3 screenshots.
- [x] **Banner** (15 min) — hand-written SVG in `docs/readme/banner.svg`
      (no binary, no external font; `docs/` is outside gate G1).
- [x] **README** (60 min) — hero + badges, feature grid, screenshots, quick start
      (with the `DATABASE_URL` requirement the old README omitted), architecture
      (Mermaid), repo map, API reference, calculation engine, deal lifecycle,
      frontend, tests/CI/nightly, deploy + env vars, "adding a deal input"
      checklist (collapsed), an **AI agents** section (invariants, conventions,
      verification commands), docs index, troubleshooting.
- [x] **Verify** (10 min) — no absolute filesystem path (gate G8), every relative link resolves, every referenced screenshot exists,
      Mermaid blocks parse.
- [x] **Commit + push** (5 min).

## Tests

A README carries no behaviour, so there are no unit/integration/E2E tests to
add. The checks that apply are the documentation gates: G8 (no absolute path;
run with `node frontend/scripts/audit/paths.mjs` once `frontend/node_modules`
is installed, or the same regexes applied by hand) and a
link check (every `](path)` target exists in the tree).

## MCP server

No endpoint or feature is added, so there is nothing to expose in an MCP server.

## Review

**Changed**

- `README.md` — rewritten from scratch (~700 lines). Hero banner and badges, a
  five-module feature table, a screenshot grid from `docs/ui-overhaul/screenshots/v3/`,
  a three-terminal quick start, three Mermaid diagrams (system, backend layering,
  deal lifecycle), an annotated repository map, the full 45-route API reference in
  collapsible groups, a `curl` example with the **real** response from the app,
  the BRRRR / Flip step tables, frontend routes and folder guide, the test and gate
  table, CI + nightly, deploy + every environment variable, the twelve-step
  "add a deal input" checklist (collapsed), a **For AI agents** section (where to
  look, invariants, proof commands, known gaps), a docs index, troubleshooting
  and a contributing checklist.
- `docs/readme/banner.svg` — new, hand-written, no external fonts or binaries.
- `tasks/todo/WebsiteReadme.md` — this file.

**Fixed along the way** (stale content in the old README)

- Quick start never said `DATABASE_URL` is required; the app raises without it.
- The "Workflow" section pointed at `/CalcPrecentageOfARVRes`, an endpoint that
  does not exist.
- Prerequisites said Python 3.10 / Node 20; `runtime.txt` pins 3.11.9 and CI uses
  Node 22.
- The nightly preview command wrote to a temp-directory path, which gate G8
  (`frontend/scripts/audit/paths.mjs`) flags; it now writes a repo-relative file.

**Verified**

- The example request was run against the real app (SQLite, scratch directory)
  and the response values in the README are the ones it returned.
- All three Mermaid blocks render (mermaid 11 in headless Chromium).
- Every relative link, image and in-page anchor resolves.
- Gate G8's regexes find nothing in the new or changed files.
- Spec counts (17 flow, 8 check), primitive count (25) and pipeline stage names
  were read from the tree, not from older docs.

**Not done / for the owner**

- The plan was not reviewed before work started (autonomous session); review it
  now together with the README diff.
- Deployment config (Netlify redirect, Render service) is still only in the
  dashboards; the README says so rather than inventing a `netlify.toml`.
