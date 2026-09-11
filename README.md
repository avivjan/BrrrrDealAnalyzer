<p align="center">
  <img src="docs/readme/banner.svg" alt="BigWhales — BRRRR Deal Analyzer" width="100%">
</p>

<h1 align="center">BigWhales · BRRRR Deal Analyzer</h1>

<p align="center">
  <strong>Underwrite a rental or a flip in seconds, track it from offer to refinance, and see every dollar of cash flow before it happens.</strong>
</p>

<p align="center">
  <a href="https://github.com/avivjan/BrrrrDealAnalyzer/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/avivjan/BrrrrDealAnalyzer/actions/workflows/ci.yml/badge.svg?branch=main"></a>
  <a href="https://github.com/avivjan/BrrrrDealAnalyzer/actions/workflows/e2e-nightly.yml"><img alt="Nightly e2e" src="https://github.com/avivjan/BrrrrDealAnalyzer/actions/workflows/e2e-nightly.yml/badge.svg"></a>
  <img alt="Python 3.11" src="https://img.shields.io/badge/python-3.11-3776AB?logo=python&logoColor=white">
  <img alt="FastAPI" src="https://img.shields.io/badge/FastAPI-backend-009688?logo=fastapi&logoColor=white">
  <img alt="Vue 3" src="https://img.shields.io/badge/Vue-3.5-42b883?logo=vuedotjs&logoColor=white">
  <img alt="TypeScript" src="https://img.shields.io/badge/TypeScript-5.9-3178C6?logo=typescript&logoColor=white">
  <img alt="PostgreSQL" src="https://img.shields.io/badge/PostgreSQL-16-4169E1?logo=postgresql&logoColor=white">
  <img alt="Playwright" src="https://img.shields.io/badge/Playwright-5_projects-2EAD33?logo=playwright&logoColor=white">
</p>

<p align="center">
  <a href="https://bigwhales.netlify.app"><b>Live app</b></a> ·
  <a href="#-quick-start">Quick start</a> ·
  <a href="#-architecture">Architecture</a> ·
  <a href="#-api-reference">API</a> ·
  <a href="#-the-calculation-engine">Calc engine</a> ·
  <a href="#-testing--quality-gates">Tests</a> ·
  <a href="#-deployment--configuration">Deploy</a> ·
  <a href="#-for-ai-agents-and-new-contributors">For AI agents</a>
</p>

---

## 🐋 What is this?

**BigWhales** is the operating console of a small real-estate investing business. It is a
single web app with a FastAPI backend that does five things:

| | Module | What it does |
| --- | --- | --- |
| 🧮 | **Analyze** | Type a deal's numbers once and get the BRRRR *or* Flip verdict instantly: cash flow, DSCR, cash-on-cash, cash left in the deal, ROI, net profit, and a line-by-line **calculation breakdown** that shows the formula behind every metric. |
| 🗂️ | **My Deals** | A Kanban board of deals being underwritten (*New → Working → Brought → Keep in Mind → Dead*). Cards auto-save and re-analyze as you tweak numbers. Duplicate, delete, copy a summary for an AI, or e-mail an offer to the listing agent. |
| 🏠 | **Bought** | Deals under contract or owned, moving through an **editable pipeline** (BRRRR: Purchase → Prepare for Closing → Closed → Rehab → Rent → Prepare for Refi → Refinanced; Flip: … → Rehab → Sell → Sold) with sub-stage checklists and per-stage stats. One click exports a branded PDF report. |
| 💧 | **Liquidity** | A cash-runway timeline: starting balance, one-off transactions and recurring rules projected day by day, with a live Mercury bank balance when configured. |
| ⏱️ | **REPS** | A Real Estate Professional Status hour tracker for two users: a timer with GPS, evidence uploads to Google Cloud Storage, and an audit log appended to a Google Sheet. |

Everything is one page app, four switchable looks (Obsidian Terminal, Aurora Glass,
Neo-Brutal Fintech, Quiet Luxury) in light and dark, a ⌘K command palette, and a
mobile layout that is tested on emulated iPhone and Pixel devices every night.

## 📸 Screenshots

<table>
  <tr>
    <td width="50%"><img src="docs/ui-overhaul/screenshots/v3/final-luxury-dark-home.png" alt="Dashboard, Quiet Luxury dark"></td>
    <td width="50%"><img src="docs/ui-overhaul/screenshots/v3/final-luxury-dark-analyze.png" alt="Analyze a deal, Quiet Luxury dark"></td>
  </tr>
  <tr>
    <td align="center"><sub><b>Dashboard</b> — portfolio KPIs and every tool one click away</sub></td>
    <td align="center"><sub><b>Analyze</b> — BRRRR / Flip toggle, the analysis runs on save</sub></td>
  </tr>
  <tr>
    <td width="50%"><img src="docs/ui-overhaul/screenshots/v3/final-luxury-dark-bought-deals.png" alt="Bought deals pipeline"></td>
    <td width="50%"><img src="docs/ui-overhaul/screenshots/v3/final-luxury-dark-liquidity.png" alt="Liquidity timeline"></td>
  </tr>
  <tr>
    <td align="center"><sub><b>Bought</b> — stage rail with sub-stage checklists</sub></td>
    <td align="center"><sub><b>Liquidity</b> — projected balance, inflows and outflows</sub></td>
  </tr>
</table>

<details>
<summary><b>More looks and the mobile layout</b></summary>
<br>
<table>
  <tr>
    <td width="50%"><img src="docs/ui-overhaul/screenshots/v3/final-aurora-dark-my-deals.png" alt="My Deals board, Aurora Glass dark"></td>
    <td width="50%"><img src="docs/ui-overhaul/screenshots/v3/final-aurora-dark-reps.png" alt="REPS tracker, Aurora Glass dark"></td>
  </tr>
  <tr>
    <td align="center"><sub><b>My Deals</b> — Aurora Glass, dark</sub></td>
    <td align="center"><sub><b>REPS tracker</b> — Aurora Glass, dark</sub></td>
  </tr>
  <tr>
    <td align="center">
      <img src="docs/ui-overhaul/screenshots/v3/final-aurora-light-390-home.png" alt="Home on a 390px phone" width="32%">
      <img src="docs/ui-overhaul/screenshots/v3/final-aurora-light-390-analyze.png" alt="Analyze on a 390px phone" width="32%">
      <img src="docs/ui-overhaul/screenshots/v3/final-aurora-light-390-liquidity.png" alt="Liquidity on a 390px phone" width="32%">
    </td>
    <td align="center">
      <img src="docs/ui-overhaul/screenshots/v3/final-aurora-light-390-my-deals.png" alt="My Deals on a 390px phone" width="32%">
      <img src="docs/ui-overhaul/screenshots/v3/final-aurora-light-390-bought-deals.png" alt="Bought on a 390px phone" width="32%">
      <img src="docs/ui-overhaul/screenshots/v3/final-aurora-light-390-reps.png" alt="REPS on a 390px phone" width="32%">
    </td>
  </tr>
  <tr>
    <td align="center" colspan="2"><sub>Aurora Glass, light, at 390 px — the iPhone 14 viewport the nightly suite runs against</sub></td>
  </tr>
</table>
<p>Every route at 390 / 768 / 1024 / 1440 px is in <code>docs/ui-overhaul/screenshots/</code>.</p>
</details>

## ⚡ Quick start

You need **Python 3.11** (`runtime.txt` pins 3.11.9), **Node 22** and **Docker** (for a
local PostgreSQL). Three terminals.

**1 · Database**

```bash
# Any PostgreSQL 14+ works. A throwaway one in Docker:
docker run -d --name bigwhales-dev -p 5432:5432 \
  -e POSTGRES_USER=bigwhales -e POSTGRES_PASSWORD=bigwhales -e POSTGRES_DB=bigwhales postgres:16
```

> No Docker? `DATABASE_URL=sqlite:///./dev.db` still boots the API for a quick look, but
> production is PostgreSQL and the migrations are written for it, so use Postgres for
> anything you intend to keep.

**2 · Backend** (FastAPI on <http://127.0.0.1:8000>, interactive docs at `/docs`)

```bash
cd BackEnd
python3 -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
export DATABASE_URL=postgresql://bigwhales:bigwhales@127.0.0.1:5432/bigwhales   # required — the app refuses to start without it
uvicorn main:app --reload
```

On import the app creates missing tables, runs the idempotent migrations in
`BackEnd/migrations/`, and seeds the default pipeline templates and REPS categories.
Every optional integration (Gmail, Mercury, Google Sheets / GCS) is **graceful**: leave its
variables unset and the matching feature reports "not configured" instead of failing.
`BackEnd/.env` is read automatically and is git-ignored.

**3 · Frontend** (Vite on <http://localhost:5173>, hot reload)

```bash
cd frontend
npm install
npm run dev
```

The UI talks to `VITE_API_URL`, defaulting to `http://localhost:8000`. Nothing else is
hard-coded. Open <http://localhost:5173>, go to **Analyze**, fill in a purchase price, ARV,
rent and a rate, and press **Analyze & Save**. The deal lands on **My Deals**.

<details>
<summary><b>Run the test suites</b></summary>

```bash
# Backend — needs the throwaway test Postgres (loopback, port 55432, data on tmpfs)
docker compose -f BackEnd/docker-compose.test.yml up -d --wait
cd BackEnd && pytest                       # results pinned to reference values, so a formula change fails loudly
python3 verify_regression.py verify        # bit-for-bit contract snapshot (OpenAPI, schema, calcs, 45 endpoints)

# Frontend
cd frontend
npm test                                   # Vitest unit + contract tests
npm run build                              # vue-tsc type-check + production bundle
npx playwright install                     # once
npm run e2e                                # Playwright, 5 projects, boots both servers itself
npm run verify:ui                          # every behaviour-freeze gate, one PASS/FAIL line each
```

See [Testing & quality gates](#-testing--quality-gates) for what each of these proves.
</details>

## 🏛️ Architecture

```mermaid
flowchart LR
    subgraph Client["Browser"]
        SPA["Vue 3 SPA<br/>Vite · Pinia · Tailwind · PrimeVue (unstyled) · GSAP"]
    end
    subgraph Netlify["Netlify"]
        Static["static build<br/>bigwhales.netlify.app"]
    end
    subgraph Render["Render"]
        API["FastAPI<br/>routers → BL → DAL"]
        PG[("PostgreSQL 16")]
    end
    subgraph External["Optional integrations"]
        Gmail["Gmail SMTP<br/>send offers"]
        Mercury["Mercury API<br/>bank balance"]
        Sheets["Google Sheets + GCS<br/>REPS audit log & evidence"]
    end
    Static -- serves --> SPA
    SPA -- "axios · VITE_API_URL" --> API
    API --> PG
    API -. EMAIL_PASSWORD .-> Gmail
    API -. MERCURY_API_TOKEN .-> Mercury
    API -. REPS_* / GOOGLE_APPLICATION_CREDENTIALS .-> Sheets
```

There are **no accounts and no auth**: the app is a private tool for one business, and the
backend's CORS allow-list (`localhost:5173`, `localhost:3000`, `bigwhales.netlify.app`) is the
only gate. Looks, theme and motion preferences persist per browser in `localStorage`.

### How a request flows through the backend

```mermaid
flowchart TB
    R["routers/&lt;division&gt;.py<br/><i>HTTP only: path, method, status codes, exception mapping — one-line delegation</i>"]
    B["BL/&lt;division&gt;/&lt;endpoint&gt;.py<br/><i>framework-agnostic business logic; plain types, Pydantic models, a Session</i>"]
    D["DAL/crud/&lt;division&gt;.py + DAL/data_models/&lt;division&gt;/<br/><i>SQLAlchemy queries only: no logic, no Pydantic, no commits</i>"]
    RR["ReqRes/common/*.py<br/><i>every Pydantic request/response model, defined once</i>"]
    DB[("PostgreSQL")]
    R --> B --> D --> DB
    R -.imports.-> RR
    B -.imports.-> RR
```

The same **nine divisions** repeat in every layer, so a feature is always found at the same
relative path: `analyze`, `reports`, `activeDeal`, `boughtDeal`, `email`, `liquidity`,
`pipelineTemplate`, `reps`, `health`. Routers are deliberately unprefixed and untagged so the
OpenAPI contract stays byte-identical to the pre-refactor app (it is snapshotted, see
[`verify_regression.py`](BackEnd/README.md#regression-harness)).

### Deal lifecycle

```mermaid
flowchart LR
    A["<b>Analyze</b><br/>POST /analyze/brrr | flip"] -->|"Analyze & Save<br/>POST /active-deals"| M
    subgraph M["<b>My Deals</b> (active deals board)"]
        direction LR
        N["New"] --> W["Working"] --> Br["Brought"]
        W --> K["Keep in Mind"]
        W --> Dd["Dead"]
    end
    M -->|"autosave on edit<br/>PUT /active-deals/{id}"| M
    M -->|"Move to Bought<br/>POST /bought-deals/from-active/{id}"| Bo
    subgraph Bo["<b>Bought</b> (pipeline template per deal type)"]
        direction LR
        P["Purchase"] --> PC["Prepare for<br/>Closing"] --> C["Closed"] --> Rh["Rehab"]
        Rh -->|BRRRR| Rn["Rent"] --> PR["Prepare<br/>for Refi"] --> Rf["Refinanced"]
        Rh -->|Flip| Se["Sell"] --> So["Sold"]
    end
    Bo -->|"POST /reports/{brrr,flip}-pdf"| PDF["Branded PDF"]
    M -->|"POST /send-offer"| Mail["Offer e-mail"]
```

*Move to Bought* **copies** the deal into the first stage of its pipeline; the active card
stays on the board. Stage ids are string slugs held in the editable pipeline template, and
every deal type (BRRRR / FLIP) has its own template.

## 🗺️ Repository map

```
.
├── BackEnd/                     FastAPI service (Python 3.11)
│   ├── main.py                  app + bootstrap + CORS + mount every router (~40 lines)
│   ├── db.py                    engine / SessionLocal / Base — reads DATABASE_URL (required)
│   ├── bootstrap.py             create_all → migrations → seed templates & REPS categories, at import
│   ├── migrations/              hand-rolled, idempotent schema migrations (no Alembic)
│   ├── routers/                 one file per division, one-line handlers
│   ├── BL/                      business logic; BL/analyze/ is the calc engine
│   │   └── analyze/{brrrSteps,flipSteps}/   one file per calculation subject
│   ├── DAL/{data_models,crud}/  SQLAlchemy tables and query functions
│   ├── ReqRes/common/           every Pydantic model, defined once
│   ├── tests/                   pytest suite + db_isolation_guard + _regression_snapshots/
│   ├── verify_regression.py     golden-snapshot harness for the whole observable contract
│   └── docker-compose.test.yml  throwaway test Postgres on 127.0.0.1:55432
├── frontend/                    Vue 3 + Vite + TypeScript SPA (Node 22)
│   ├── src/{views,components,stores,api,utils,types,config,router}/
│   ├── src/{design,motion,assets}/          tokens, looks, GSAP layer
│   ├── e2e/                     Playwright characterization suite + network goldens
│   ├── scripts/audit/           the verify:ui gate implementations
│   └── README.md                the UI guide: tokens, primitives, motion rules, gates
├── .github/workflows/           ci.yml (PR + push) · e2e-nightly.yml (midnight Israel time)
├── .github/scripts/nightly/     the nightly HTML e-mail report package
├── docs/                        plans, decisions, quality snapshots, screenshots
├── design-system/               generated + annotated design-system reference (docs only)
├── tasks/                       working plans (tasks/todo/<Task>.md) — see .claude/CLAUDE.md
├── REPS_README.md               Google Cloud setup for the REPS tracker
└── runtime.txt                  Python version pin for Render
```

## 🔌 API reference

Every route, grouped by division. `{deal_type}` is `BRRRR` or `FLIP`. The live OpenAPI
document is at `/docs` on a running backend.

<details open>
<summary><b>Analyze & reports</b></summary>

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/analyze/brrr` | Validate and run the BRRRR calculation; returns metrics, messages and breakdowns |
| `POST` | `/analyze/flip` | Same for a Flip |
| `POST` | `/reports/brrr-pdf` | Branded BRRRR PDF. Query: `address`, `disposition=inline\|attachment` |
| `POST` | `/reports/flip-pdf` | Same for a Flip |
</details>

<details>
<summary><b>Active deals (My Deals board)</b></summary>

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/active-deals` | List every active BRRRR and Flip deal |
| `POST` | `/active-deals` | Create one (body is the BRRRR or Flip create model) |
| `PUT` | `/active-deals/{id}` | Full update: **every** field is written, so defaults matter |
| `DELETE` | `/active-deals/{id}?deal_type=` | Delete |
| `POST` | `/active-deals/{id}/duplicate?deal_type=` | Clone |
</details>

<details>
<summary><b>Bought deals & pipeline templates</b></summary>

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/bought-deals` | List |
| `POST` | `/bought-deals` | Create directly |
| `PUT` | `/bought-deals/{id}` | Full update (stage, sub-stage ticks, numbers) |
| `DELETE` | `/bought-deals/{id}?deal_type=` | Delete |
| `POST` | `/bought-deals/from-active/{id}?deal_type=` | Copy an active deal into the first pipeline stage |
| `GET` | `/pipeline-templates` | Both templates |
| `PUT` | `/pipeline-templates/{deal_type}` | Replace a template's stages |
| `GET` | `/pipeline-templates/{deal_type}/stats` | Deal counts per stage |
</details>

<details>
<summary><b>Liquidity</b></summary>

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` `POST` | `/liquidity/transactions` | One-off transactions |
| `PUT` `DELETE` | `/liquidity/transactions/{id}` | |
| `GET` `POST` | `/liquidity/recurring` | Recurring rules |
| `PUT` `DELETE` | `/liquidity/recurring/{id}` | |
| `GET` `PUT` | `/liquidity/settings` | Starting balance and horizon |
| `GET` | `/liquidity/mercury-balance` | Live bank balance; `503` when no token is configured |
</details>

<details>
<summary><b>REPS tracker</b></summary>

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/reps/log` | Log an activity → appends a row to the user's Google Sheet |
| `GET` | `/reps/entries?user=` | Entries for a user |
| `POST` | `/reps/upload`, `/reps/upload-batch` | Evidence files → GCS |
| `GET` `POST` | `/reps/properties` | Prospects for the dropdown |
| `DELETE` | `/reps/properties/{id}` | |
| `GET` `POST` | `/reps/people` | People involved |
| `PUT` `DELETE` | `/reps/people/{id}` | |
| `GET` `POST` | `/reps/activity-categories` | Categories |
| `DELETE` | `/reps/activity-categories/{id}` | |
| `GET` | `/reps/config-status` | `{configured: bool, …}` — is Google wired up |
</details>

<details>
<summary><b>Other</b></summary>

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/send-offer` | E-mail an offer to a listing agent over Gmail SMTP |
| `GET` | `/helloworld` | Liveness probe; also the Playwright readiness URL |
</details>

### Try it

Prices are entered **in thousands** (`purchasePrice: 200` is $200,000); rent, taxes and
insurance are in dollars; rates are percentages. The field names are the ones the UI's
`DealInputsForm` emits, camelCase aliases included.

```bash
curl -s http://127.0.0.1:8000/analyze/brrr -H 'content-type: application/json' -d '{
  "purchasePrice": 200, "rehabCost": 50, "rehabContingency": 10, "closingCostsBuy": 5,
  "down_payment": 20, "hmlPoints": 2, "HMLInterestRate": 11, "use_HM_for_rehab": true,
  "arv_in_thousands": 320, "daysUntilRefi": 180, "closingCostsRefi": 6, "refiPoints": 1.5,
  "cashReserve": 0, "loanTermYears": 30, "ltv_as_precent": 75, "interestRate": 6.5,
  "rent": 2600, "vacancyPercent": 5, "property_managment_fee_precentages_from_rent": 8,
  "maintenancePercent": 5, "capexPercent": 5,
  "annual_property_taxes": 3600, "annual_insurance": 1200, "montly_hoa": 0
}'
```

```jsonc
{
  "cash_flow": 85.04, "dscr": 1.36, "cash_out": -48125.0, "cash_out_routi": 15400.0,
  "cash_on_cash": 2.12, "roi": 68.35, "equity": 80000.0, "net_profit": 31875.0,
  "total_cash_needed_for_deal": 63525.0, "total_cash_needed_for_deal_with_buffer": 76637.5,
  "messages": null,
  "breakdowns": {                       // one list of CalcStep per metric; the PDF renders these
    "cash_flow": [
      { "label": "Monthly Operating Expenses", "value": 998.0,
        "unit": "money",
        "formula": "Vacancy 5% of rent ($130) + Management 8% of rent ($208) + Maintenance 5% of rent ($130) + CapEx 5% of rent ($130) + Taxes ÷ 12 ($300) + Insurance ÷ 12 ($100) + HOA ($0) = $998",
        "terms": [ { "label": "Vacancy 5% of rent", "value": 130, "sign": "+" }, "..." ] },
      { "label": "Monthly Mortgage Payment", "value": 1516.96,
        "unit": "money",
        "formula": "Refi Loan ($240,000) amortized at 6.5%/yr over 30 years = $1,516.96" },
      { "label": "Net Operating Income (NOI)", "value": 1602.0,
        "unit": "money", "formula": "Rent ($2,600) − Operating Expenses ($998) = $1,602",
        "terms": [ { "label": "Rent", "value": 2600, "sign": "+" }, { "label": "Operating Expenses", "value": 998, "sign": "-" } ] },
      { "label": "Monthly Cash Flow", "value": 85.04,
        "unit": "money", "formula": "NOI ($1,602) − Mortgage ($1,516.96) = $85.04",
        "terms": [ { "label": "NOI", "value": 1602, "sign": "+" }, { "label": "Mortgage", "value": 1516.96, "sign": "-" } ] }
    ],
    "dscr": [ /* … */ ], "cash_out": [ /* … */ ], "roi": [ /* … */ ]
  }
}
```

(Values rounded here; the API returns full-precision floats. A negative `cash_out` means
cash is left in the deal after the refinance.)

<details open>
<summary><b>Compact deal views (both boards)</b></summary>

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/deals` | Compact rows across the My Deals and Bought Deals boards, no breakdowns. Query: `board=all\|active\|bought`, `deal_type`, `stage`, `q` (words in address, notes, task, niche, contact), `limit` |
| `GET` | `/deals/search` | Same rows, `q` required |
| `GET` | `/deals/portfolio` | Counts by board/type/stage, totals over bought deals, top deals by equity, cash flow and cash-on-cash |
| `GET` | `/deals/{deal_id}` | One deal in full (inputs, metrics, breakdowns, comps), whichever board it is on |
</details>

### MCP server (Claude connector)

Every route above is also an **MCP tool**, so Claude can use the site directly: analyze
and save deals, move them across the boards, render the PDF reports, manage the liquidity
timeline and pipeline templates, log REPS hours, send offers. `BackEnd/mcp_server.py`
builds the tool list from the app's own OpenAPI document and executes each call against the
app in-process, so nothing is duplicated and a new endpoint becomes a tool automatically —
give it a line in `DESCRIPTIONS` there, or `tests/test_mcp.py` fails.

For deal questions a chat should start with the compact tools (`portfolio_summary`,
`list_deals`, `search_deals`) and use `get_deal` for one deal's breakdown; the full board
dumps (`get_active_deals`, `get_bought_deals`) are megabytes. Tests keep this true:
`tests/test_mcp.py` checks that a table of user phrases ("best deal", "properties we
bought", "log hours", ...) each match a tool's name or description, that the compact
tools stay under a size budget with 70 deals seeded, and that every tool carries the
right read-only / destructive annotation. The nightly's **MCP connector probe** job asks
Claude the real question through the API with the connector attached and fails unless a
compact tool was used and the answer quotes the money left in a bought deal correctly
(needs the `ANTHROPIC_API_KEY` and `MCP_PROBE_URL` secrets; it skips without them).

Every output is explained, not just every input: each result field carries a description
with its unit and sign convention (for example `cash_out` negative = money still left in
the deal; `cash_out_routi` = the cash wire received at the refinance closing table), every
JSON tool publishes an output schema built from those descriptions and returns structured
content that validates against it, and the server instructions carry a glossary. The
compact rows add `cash_left_in_deal` and `cash_wire_at_refi` so the common questions need no
sign reading at all. A test fails on any undocumented output field.

The transport is stateless Streamable HTTP, served by the same `uvicorn` process at
`/mcp/<MCP_PATH_SECRET>`. Set `MCP_PATH_SECRET` (any long random string) on the Render
service; without it the endpoint is served unprotected at `/mcp`, which is only meant for
local development. The API itself has no authentication, so keep the URL private.

- **claude.ai**: Settings → Connectors → *Add custom connector* → URL
  `https://brrrrdealanalyzer.onrender.com/mcp/<MCP_PATH_SECRET>`, no OAuth.
- **Claude Code**: `claude mcp add --transport http brrrr https://brrrrdealanalyzer.onrender.com/mcp/<MCP_PATH_SECRET>`
- **Locally**: start the backend and point a client at `http://127.0.0.1:8000/mcp`.

## 🧮 The calculation engine

`BackEnd/BL/analyze/` is the core of the product, split in two so the math stays clean and the
explanation cannot drift from it:

* **The engine.** `compute_brrr(payload)` / `compute_flip(payload)` run the calculation and return a
  frozen `BrrrCalc` / `FlipCalc` record (`brrr_calc.py`, `flip_calc.py`) holding every number the
  calculation produces: dollar basis, intermediates and headline metrics, as unrounded `Decimal`s.
  The orchestrator reads top-to-bottom as the calculation itself; each line calls one pure step
  from `brrrSteps/` / `flipSteps/`, and the shared primitives live in `common/deal_math.py`. No
  strings, no formatting, nothing about the PDF.
* **The explanation.** `explain/brrr.py` / `explain/flip.py` read the finished record and build the
  `breakdowns` the PDF renders and the API and MCP pass through. Every value comes from the record;
  every equation a step narrates is first checked against it (`check`, or the fold inside
  `add_sum`), so a change to the math that is not mirrored in the text raises
  `CalcExplainMismatch` instead of printing a stale formula. `tests/test_explain.py` also fails if a
  record field is added and never explained.
* **`analyze_*`** (validate, then calculate; what the route calls) and **`calculate_*_results`**
  (calculation plus explanation, no validation; used when a saved deal is re-read and by the PDF
  reports) sit on top. Both accept the request model **or** an ORM row.

| # | BRRRR step (`brrrSteps/`) | Produces | | # | Flip step (`flipSteps/`) | Produces |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | `dollar_basis` | dollar basis, rehab with contingency | | 1 | `dollar_basis` | dollar basis, rehab with contingency |
| 2 | `hml_and_holding_costs` | hard-money amount, interest & points, pre-refi holding costs | | 2 | `hml_costs` | HML amount, points, interest over the hold |
| 3 | `operating_expenses` | monthly operating expenses and their components | | 3 | `holding_costs` | monthly operating, `total_holding_costs` |
| 4 | `refi_terms` | refi closing costs, points, LTV, reserve | | 4 | `selling_costs` | agent fees, selling closing costs |
| 5 | `cash_out` | `cash_out`, `cash_out_routi`, refi loan, total cash invested | | 5 | `total_cash_needed` | `total_cash_needed(_with_buffer)` and the buffer components |
| 6 | `mortgage_payment` | monthly DSCR-loan payment | | 6 | `cost_basis` | cash invested, cost basis, gross profit |
| 7 | `cash_flow` | NOI, **`cash_flow`** | | 7 | `net_profit` | capital-gains tax, **`net_profit`** |
| 8 | `dscr` | PITIA, **`dscr`** | | 8 | `roi` | **`roi`**, `annualized_roi` |
| 9 | `cash_on_cash` | **`cash_on_cash`** | | | | |
| 10 | `equity_and_net_profit` | `equity`, `net_profit` | | | | |
| 11 | `roi` | **`roi`** | | | | |
| 12 | `total_cash_needed` | `total_cash_needed_for_deal(_with_buffer)` and the buffer components | | | | |

Each breakdown step carries a `unit` (`money`, `pct` or `ratio`), the `formula` with the numbers
filled in, an optional `note`, and, on sum-type steps, the `terms` that add up to its value, which
the PDF stacks one operand per line. Sum-type totals in `deal_math.py` are flat left-to-right sums
in the order the explanation lists the terms; that is what lets the guard use exact equality on
unrounded Decimals. Sentinel values `-1` and `-2` render as `∞` and `-∞`.
`tests/test_analyze.py` pins the reference results, so a formula change fails loudly.

**To add a metric or an intermediate:** compute it in the engine and add a field to the record;
`tests/test_explain.py` then tells you it is unexplained; add its step in `explain/` (an `add_sum`
with the terms in the engine's order, or an `add` with a `check`); add it to `*_SECTIONS` if it is a
headline metric, and the PDF summary and sections follow.

## 🎨 Frontend

Vue 3.5 · Vite 7 · TypeScript 5.9 · Pinia 3 · Vue Router 4 · Tailwind 3.4 · PrimeVue 4
(**unstyled**, one global pass-through preset) · GSAP 3.15 · vue-draggable-plus · axios.
Support floor: iOS/Safari 15.4+ and Chrome 108+.

| Route | View | What's there |
| --- | --- | --- |
| `/` | `LandingPage.vue` | Dashboard: doors, value, debt, equity; tool tiles; professional resources |
| `/analyze` | `AnalyzeDeal.vue` | BRRRR / Flip form with a live summary rail |
| `/my-deals` | `MyDeals.vue` | Five stage columns, drag-and-drop, card modal with autosave |
| `/bought-deals` | `BoughtDeals.vue` | Stage-rail board, sub-stage checklists, template editor, PDF |
| `/liquidity` | `LiquidityTimeline.vue` | Balance line, transactions, recurring rules, settings |
| `/reps` | `RepsTracker.vue` | Timer, entries, people, prospects, evidence upload |

| Folder (`frontend/src/`) | Holds |
| --- | --- |
| `api/` | the one axios client (`VITE_API_URL`) and every call |
| `stores/` | six Pinia stores: deals, bought deals, pipeline templates, liquidity, REPS, connection |
| `utils/` | `dealUtils.ts` (empty form, defaults, validation, clipboard summary), `liquidityEngine.ts` (pure timeline math), `money.ts` |
| `types/`, `config/` | request/response types; bought-deal stage definitions and `canAdvance` |
| `components/` | feature components; `ui/` 25 globally registered `Ui*` primitives; `shell/` sidebar, topbar, mobile nav, ⌘K, settings; `board/`, `liquidity/`, `reps/` |
| `design/` | `tokens` runtime, `looks.ts`, `theme.ts`, `cn.ts`, `primevue-pt.ts` |
| `motion/` | GSAP presets (`page`, `modal`, `hero`, …) and directives (`v-reveal`, `v-press`, `v-tilt`, `v-count-up`, …) |
| `assets/` | `tokens.css` (single source of truth) and the four generated `looks/*.css` |

The three places a user types deal numbers (Analyze, the My Deals modal, the Bought modal)
render the **same** `DealInputsForm.vue`, which mutates the deal object in place so the
modals' deep watchers drive autosave and re-analysis.
[`frontend/README.md`](frontend/README.md) is the full guide: design tokens, primitives,
looks, the motion rules a change must not break, and the gate set.

## ✅ Testing & quality gates

| Layer | Command | What it proves |
| --- | --- | --- |
| Backend unit + API | `cd BackEnd && pytest` | `/analyze/*` results pinned to reference values, deal CRUD, duplicate/delete, move-to-bought, autosave, PDF reports, the DB isolation guard itself |
| MCP server | part of `cd BackEnd && pytest` (`tests/test_mcp*.py`, discovered like any other file) | All 45 tools exist with valid schemas, every feature area works through its tool, and a real `uvicorn` with a path secret answers the official MCP client over Streamable HTTP |
| Backend contract | `python3 verify_regression.py verify` | OpenAPI, every ORM column, every Pydantic model, every metric across ~40 payloads and a scripted pass through all 45 endpoints — bit-for-bit against `tests/_regression_snapshots/` |
| Frontend unit | `cd frontend && npm test` | Vitest: component contracts, stores, engines, the e2e **hook inventory** |
| Frontend build | `npm run build` | `vue-tsc` type-check + Vite production bundle (what Netlify runs) |
| End-to-end | `npm run e2e` | Playwright: 17 flow specs replay every user journey and assert its **exact HTTP contract** against committed goldens; 8 check specs cover axe, CLS, modal scroll, theme, no live tweens |
| The whole gate set | `npm run verify:ui` (`--fast` skips the browser, `--phase` adds the backend proofs) | G1 nothing outside `frontend/` moved · G2 behavioural dirs byte-identical · G-HOVER touch fallbacks · **G8 no absolute filesystem path in any tracked file** · G6 test + build · G5/G7 Playwright · GOLDEN-POLICY goldens only change in `Golden update:` commits |

**Database safety.** The backend suites never touch `DATABASE_URL`. `tests/conftest.py`
overwrites it with `TEST_DATABASE_URL` (default: the compose container on
`127.0.0.1:55432`) *before* any application module is imported, stubs out `load_dotenv`,
and then verifies at import, at session start and before every test that the engine is
PostgreSQL, on a loopback host, on a database whose name ends in `_test`, with no hosted
provider marker in the URL. Otherwise the run aborts with a `TEST DATABASE SAFETY ABORT`
banner. This matters because a Render pre-deploy command runs with the production URL in
its environment.

**Playwright** boots both servers itself: the real FastAPI app on `:8011` against the
throwaway Postgres with every credential scrubbed, and a production build on `:5173`. Five
projects: `chromium`, `webkit`, `Mobile Safari` (iPhone 14), `Mobile Chrome` (Pixel 7), all
with reduced motion, plus `chromium-motion` for the `@motion` specs.

### CI and the nightly

- **`ci.yml`** runs on every pull request and every push to `main`: **Backend tests**
  (pytest on a `postgres:16` service, a migration smoke that boots the app twice against a
  fresh database, the nightly package's unit tests; pytest discovers every
  `tests/test_*.py`, the MCP server files included, so a new test file needs no workflow
  edit) and **Frontend tests + build**. Make those two checks required under
  *Settings → Branches → main* to block red merges.
- **`e2e-nightly.yml`** runs at midnight Israel time (two crons, a gate job picks the one
  that is 00:xx in Asia/Jerusalem) and on demand: the CI jobs, the full Playwright matrix
  and the MCP connector probe (see the MCP section above).
  When every job has finished, a styled HTML report is e-mailed over Gmail SMTP, pass or
  fail. It needs the repository secrets `NIGHTLY_MAIL_USERNAME` and `NIGHTLY_MAIL_PASSWORD`
  (a Gmail app password). The report explains every skipped test against
  `.github/nightly/known_skips.json`, flags anomalies, breaks each suite down and draws
  trend charts from `history.jsonl` on the orphan branch `nightly-history`.

<p align="center">
  <img src="docs/nightly/preview-pass.png" alt="Nightly report e-mail, passing" width="49%">
  <img src="docs/nightly/preview-fail.png" alt="Nightly report e-mail, failing" width="49%">
</p>

<details>
<summary>Preview the nightly e-mail locally without sending</summary>

```bash
python3 .github/scripts/nightly/make_preview_fixtures.py          # writes .github/scripts/nightly/out/{pass,fail}
python3 .github/scripts/nightly_e2e_email.py \
  --playwright .github/scripts/nightly/out/fail/report.json \
  --history .github/scripts/nightly/out/fail/history.jsonl \
  --write-html nightly-preview.html --no-send
python3 -m unittest discover -s .github/scripts/nightly/tests -t .github/scripts
```

A Playwright spec that skips on some projects must add or bump its reason in
`known_skips.json` in the same PR, or the next nightly flags it.
</details>

## 🚀 Deployment & configuration

| Piece | Where | How |
| --- | --- | --- |
| Frontend | **Netlify** → <https://bigwhales.netlify.app> | Build `npm run build` in `frontend/`; set `VITE_API_URL` to the backend URL. The router uses history mode, so deep links need the SPA redirect (`/* → /index.html 200`) configured in the Netlify UI. There is no `netlify.toml` in the repo. |
| Backend | **Render** web service | Python from `runtime.txt`, `pip install -r BackEnd/requirements.txt`, a `uvicorn main:app` start command from `BackEnd/`. Set **Pre-Deploy Command** to `cd BackEnd && pytest` to gate a deploy on the suite (that is why `pytest` and `httpx` are in `requirements.txt`, and why `pytest.ini` disables the cache for the read-only filesystem). No `render.yaml` in the repo. |
| Database | Render PostgreSQL | `DATABASE_URL`; schema is created and migrated at boot |

Neither test suite runs inside a Netlify build. A new frontend origin must be added to the
CORS allow-list in `BackEnd/main.py`.

### Environment variables

| Variable | Used by | Notes |
| --- | --- | --- |
| `DATABASE_URL` | `BackEnd/db.py` | **Required.** `postgresql://…` in production |
| `VITE_API_URL` | `frontend/src/api/index.ts` | Build-time. Defaults to `http://localhost:8000` |
| `EMAIL_PASSWORD` | `/send-offer` | Gmail app password for the sending account; unset → `{success: false}` |
| `MERCURY_API_TOKEN`, `MERCURY_API_TOKEN_<LABEL>` | `/liquidity/mercury-balance` | One per workspace; the suffix is the label |
| `REPS_SHEET_ID_AVIV`, `REPS_SHEET_ID_YARDEN` | REPS | One Google Sheet per user |
| `REPS_GCS_BUCKET`, `REPS_GCS_BASE_PREFIX` | REPS | Evidence bucket and prefix (default `evidence/2026`) |
| `REPS_SHEET_TAB` | REPS | Default `Log` |
| `REPS_LINK_STYLE` | REPS | `public` (default) · `auth` · `signed` |
| `GOOGLE_APPLICATION_CREDENTIALS` | REPS | Path to the service-account JSON |
| `MCP_PATH_SECRET` | `BackEnd/mcp_server.py` | Secret path segment of the MCP endpoint (`/mcp/<secret>`); unset → unprotected `/mcp` with a startup warning |
| `TEST_DATABASE_URL` | tests only | Defaults to the compose container |
| `NIGHTLY_MAIL_USERNAME`, `NIGHTLY_MAIL_PASSWORD` | GitHub Actions secrets | Nightly e-mail |
| `ANTHROPIC_API_KEY`, `MCP_PROBE_URL` | GitHub Actions secrets | Nightly MCP connector probe (optional; the job skips without them) |

The full Google Cloud walk-through for the REPS tracker (project, service account, bucket,
sheets, smoke test) is [`REPS_README.md`](REPS_README.md).

## 🧩 Adding an input to the deal form

<details>
<summary>The twelve-step checklist (also in the header comment of <code>DealInputsForm.vue</code>)</summary>

**Frontend**

1. **`components/DealInputsForm.vue`** — add the `<MoneyInput>` / `<NumberInput>` /
   `<SliderField>` to the right section. Read with `get('field')`, write with
   `set('field', v)`. This is the only UI edit.
2. **`types/index.ts`** — add the field to `BaseDealReq` (shared) or to `BrrrAnalyzeReq` /
   `FlipAnalyzeReq`. `DealInputModel`, `BrrrDealCreate`, `FlipDealCreate` and
   `AnalyzeDealReq` derive from those.
3. **`utils/dealUtils.ts`** — a starting value in `createEmptyDealForm`. A BRRRR field with
   a *server* default also goes in `BRRR_LEGACY_DEFAULTS` so `ensureBrrrLegacyDefaults`
   backfills deals saved before it existed. Add a line to `formatDealForClipboard` if it
   belongs in the "Copy Summary for AI" text.
4. **`utils/dealUtils.ts`** — bounds checks in `validateDealInputs`.

**Backend**

5. **`ReqRes/common/analyze_inputs.py`** (`analyzeBRRRReq` / `analyzeFlipReq`) *and*
   **`ReqRes/common/active_deal_schemas.py`** (`BaseDealReq`, or `BrrrActiveDealCreate` /
   `FlipActiveDealCreate`). `bought_deal_schemas.py` inherits from these. The per-endpoint
   `ReqRes/<division>/<endpoint>/` files only re-export. **The Pydantic `alias=` must
   exactly match the field name used in step 1.**
6. **`ReqRes/common/analyze_results.py`** — only for a computed *output* metric.
7. **`DAL/data_models/`** — the `Column` on `common/base_deal.py`'s `BaseDeal` mixin, or on
   **all four** of `activeDeal/deals.py` and `boughtDeal/deals.py`'s deal tables. Column
   name is the non-aliased snake_case name.
8. **`migrations/runner.py`** — `add_column_if_missing` for every existing table (pattern
   in `migrations/steps/`). `create_all` only creates *new* tables. The migration
   `DEFAULT` must equal the model `default=` and the Pydantic default, because
   `update_*_deal` dumps every field on each PUT.
9. **`BL/analyze/brrrSteps/`** / **`flipSteps/`** — use the field in the step that owns
   the subject and register its `CalcStep` there. Range / sign check in
   `BL/analyze/common/validation.py`.
10. **`DAL/crud/`** — no change expected; they iterate `__table__.columns`. Confirm only.
11. **`BL/reports/common/deal_pdf.py`** — only if it is a headline metric.

**Then**

12. Extend `components/DealInputsForm.test.ts`, run `npm test` and `npm run build`, update
    the regression snapshots (`python3 verify_regression.py snapshot`, review the diff),
    and smoke-test all three pages.
13. **MCP.** The field reaches Claude automatically through the tools generated from
    OpenAPI (`BackEnd/mcp_server.py`). If you added or renamed an *endpoint*, give it a
    line in `DESCRIPTIONS` there; `tests/test_mcp.py` fails otherwise.
</details>

## 🤖 For AI agents and new contributors

This section is written so an agent dropped into a fresh checkout can be productive without
reading the whole tree.

**The working agreement** is [`.claude/CLAUDE.md`](.claude/CLAUDE.md): write a plan to
`tasks/todo/<NameOfTask>.md` first, with a time estimate on every item and the tests each
change needs; check in before starting; tick items off as you go; keep every change as small
and simple as possible; finish with a **Review** section in the same file.

### Where to look

| I want to… | Start at |
| --- | --- |
| change a formula or add a metric | `BackEnd/BL/analyze/{brrrSteps,flipSteps}/<subject>.py` and the `BrrrCalc`/`FlipCalc` record, its step in `BL/analyze/explain/`, then `tests/test_analyze.py`, `tests/test_explain.py` and the regression snapshots |
| add a field to the deal form | the [twelve-step checklist](#-adding-an-input-to-the-deal-form) above |
| add or change an endpoint | `routers/<division>.py` → `BL/<division>/<endpoint>.py` → `DAL/crud/<division>.py` → `ReqRes/common/`; then `verify_regression.py snapshot` |
| change what a page does | `frontend/src/views/<Page>.vue` and its store in `src/stores/`; re-record the network golden with `npm run e2e:record` in a separate `Golden update:` commit |
| restyle something | `frontend/src/assets/tokens.css` and the `Ui*` primitives in `src/components/ui/`; never a PrimeVue theme, never a new PrimeVue component |
| add or change a look | `frontend/scripts/design/looks.data.mjs` → `npm run build:looks` → `src/design/looks.ts` |
| touch motion | `frontend/src/motion/`; read the "rules a change must not break" in `frontend/README.md` first |
| change the schema | `DAL/data_models/` **and** an idempotent step in `BackEnd/migrations/` |
| change CI or the nightly | `.github/workflows/`, `.github/scripts/nightly/` (has its own unittest suite) |

### Invariants to keep

- **Every deal number is `Decimal` on the backend.** Prices are in thousands, rates are
  percentages. Sentinels `-1` / `-2` mean `∞` / `-∞`.
- **Layers point one way.** `routers → BL → DAL`. BL never sees a FastAPI request;
  DAL never commits or builds Pydantic; `ReqRes/common/` is the one place a model is defined.
- **Routers stay unprefixed and untagged**, and `verify_regression.py` must still pass, or
  the OpenAPI snapshot must be re-recorded deliberately.
- **`PUT` writes every field**, so a new column needs the same default in the model, the
  Pydantic schema and the migration.
- **`DealInputsForm` mutates in place** and is shared by three pages. Do not make it emit
  a replacement object.
- **No absolute filesystem path in any tracked file** (gate G8: no macOS or Linux home
  directory, no Windows drive letter, no temp directory; write `<path-to>/…` instead).
  No suppression comment exists on purpose.
- **Goldens change only in `Golden update:` commits** that change nothing else
  (`e2e/golden`, `e2e/reports`, `e2e/flows`, `e2e/fixtures`, `scripts/audit/golden`,
  `scripts/audit/allowlist.json`), logged in `docs/ui-overhaul/golden-update-log.md`.
- **Tests never see the real database.** Do not weaken `tests/db_isolation_guard.py`.
- **Motion never delays a mount**, never touches SortableJS, and the page transition stays
  opacity-only. The reasons are in `frontend/README.md`.
- **A Playwright skip needs a reason in `.github/nightly/known_skips.json`.**

### Prove a change before you push

```bash
cd BackEnd && pytest && python3 verify_regression.py verify     # backend
cd frontend && npm test && npm run build                          # frontend, fast
cd frontend && npm run verify:ui -- --fast                        # every static gate
cd frontend && npm run verify:ui -- --phase                       # the full proof, including Playwright and the backend
```

CI runs the first two lines and the build on every pull request; the nightly runs the
same jobs and the Playwright matrix, and its e-mail breaks the MCP tests out of the backend
run by module name.

### Known gaps

- `POST /reps/people` with a duplicate name returns the driver's raw error text.
- Deployment config (Netlify redirect, Render service) is not in version control.
- The two CI checks are not yet required status checks on `main`.
- The REPS prospect endpoints never expose a prospect id (create and list return name +
  source only), so the delete route can only be driven from the database.

## 📚 Documentation index

| Document | What it is |
| --- | --- |
| [`frontend/README.md`](frontend/README.md) | The UI guide: tokens, primitives, looks, shell, motion rules, the gate set, the e2e suite |
| [`BackEnd/README.md`](BackEnd/README.md) | Backend layout, tests, the regression harness |
| [`REPS_README.md`](REPS_README.md) | Google Cloud setup for the REPS tracker |
| [`.claude/CLAUDE.md`](.claude/CLAUDE.md) | The working agreement for agents |
| [`docs/ui-overhaul/decisions.md`](docs/ui-overhaul/decisions.md) | Every design and execution decision of the UI overhaul, and what it postponed |
| [`docs/ui-overhaul/primitives.md`](docs/ui-overhaul/primitives.md) | The contract of each `Ui*` primitive |
| [`docs/ui-overhaul/device-checklist.md`](docs/ui-overhaul/device-checklist.md) | The manual iPhone / desktop pass emulation cannot replace |
| [`docs/ui-overhaul/golden-update-log.md`](docs/ui-overhaul/golden-update-log.md) | Every `Golden update:` commit and why |
| [`docs/ui-overhaul/v3-quality-snapshot.md`](docs/ui-overhaul/v3-quality-snapshot.md) | axe, CLS, bundle and contrast numbers at the end of UI v3 |
| [`docs/plans/`](docs/plans/) | The UI v2 and v3 plans and progress logs |
| [`design-system/brrrr-deal-analyzer/MASTER.md`](design-system/brrrr-deal-analyzer/MASTER.md) | The design-system reference the tokens came from (the "Approved overrides" section wins) |
| [`tasks/todo.md`](tasks/todo.md) | The running work log: UI v3, CI, Postgres-everywhere, the nightly report |
| [`tasks/todo/McpServer.md`](tasks/todo/McpServer.md) | The MCP server: plan, tests, CI/nightly wiring and reviews |

## 🔧 Troubleshooting

<details>
<summary><code>RuntimeError: DATABASE_URL environment variable is not set.</code></summary>

The backend needs it before anything imports. Export it in the shell or put it in
`BackEnd/.env`.
</details>

<details>
<summary>The UI shows "Server Disconnected" / requests fail with a CORS error</summary>

The backend is not running on the URL in `VITE_API_URL`, or the frontend is served from an
origin that is not in the allow-list in `BackEnd/main.py`. Vite on `5173` and `3000` are
allowed; a different port is not.
</details>

<details>
<summary><code>TEST DATABASE SAFETY ABORT</code></summary>

The suite refused to run because the engine it resolved is not a loopback PostgreSQL with a
`_test` database. Start the throwaway container
(`docker compose -f BackEnd/docker-compose.test.yml up -d --wait`) or point
`TEST_DATABASE_URL` at one that satisfies the guard. Never point it at a real database.
</details>

<details>
<summary>Playwright says <code>command not found</code> / no browser</summary>

`npx playwright install` once. In a sandbox that cannot download browsers set
`PW_CHROMIUM_PATH` to a system Chromium.
</details>

<details>
<summary>Gate G8 fails on a documentation change</summary>

An absolute path is a fact about one laptop. Replace it with a repo-relative path or a
`<path-to>/…` placeholder. `node scripts/audit/paths.mjs` (from `frontend/`) lists every
offending line.
</details>

<details>
<summary><code>pytest</code> fails with <code>command not found</code> on Render</summary>

`pytest` and `httpx` are installed from `BackEnd/requirements.txt`; the pre-deploy command
must run after the build step that installs it, and must `cd BackEnd` first.
</details>

## 🤝 Contributing

1. Branch from `main`. Write commit subjects as a short imperative line; a golden
   re-record is its own `Golden update: <what>` commit that changes nothing else.
2. Keep the change small; write the plan in `tasks/todo/<Task>.md` first.
3. Run the [proof commands](#prove-a-change-before-you-push) that apply.
4. Open a pull request. CI must be green: **Backend tests** and **Frontend tests + build**.

<p align="center"><sub>Built for Big Whales LLC · FastAPI + Vue · tested every night on five browsers</sub></p>
