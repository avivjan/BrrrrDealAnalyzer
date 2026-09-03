# BrrrrDealAnalyzer

## Prerequisites

- Python 3.10+ (for the FastAPI backend)
- Node not required; frontend is static HTML/JS

## Run the FastAPI backend

1. Open a terminal and move into the backend folder:
   ```bash
   cd BackEnd
   ```
2. (Optional but recommended) Create and activate a virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Start the API server (listens on http://127.0.0.1:8000):
   ```bash
   uvicorn main:app --reload
   ```

## Run the frontend

1. In a separate terminal, serve the static files from the `FrontEnd` directory:
   ```bash
   cd FrontEnd
   python -m http.server 5500
   ```
   Then open http://localhost:5500 in your browser.
2. The frontend expects the backend at http://localhost:8000. If you run the API on a different host/port, update the `fetch` URL in `FrontEnd/script.js`.

## Workflow

- Start the backend first so the acquisition calculator can reach the `/CalcPrecentageOfARVRes` endpoint.
- Refresh the browser after backend changes; frontend updates hot-reload when you refresh.

## Tests

**Backend** (`pytest`, in `BackEnd/tests/`):

```bash
cd BackEnd
pip install -r requirements.txt
pytest
```

Covers `/analyze/brrr` + `/analyze/flip` (with the BRRRR and Flip results pinned
to reference values, so a formula change fails loudly), active-deal CRUD,
duplicate/delete, Move to Bought, bought-deal autosave, and the PDF reports.

> **Database safety.** `BackEnd/tests/conftest.py` redirects `$DATABASE_URL` to a
> throwaway SQLite file *before* any application module is imported — which it
> has to, because `db.py` builds its `Engine` at import time and `main.py` runs
> `bootstrap.run(...)` (schema `create_all` + the migrations in `BackEnd/migrations/`
> + seeding) at import time. It also stubs out `load_dotenv` so `BackEnd/.env`
> credentials never enter a test process.
>
> The redirect is then **verified**, at import, at session start, and before every
> test: if the engine is not the temp SQLite file — or its URL contains a
> Postgres/MySQL/Render/AWS marker — the run aborts with a
> `TEST DATABASE SAFETY ABORT` banner instead of continuing. This matters because
> a Render pre-deploy command runs with the production `DATABASE_URL` in its
> environment. `tests/test_db_isolation.py` asserts the guard itself fires.
>
> `BackEnd/db.py` is untouched by any of this — normal runtime still reads
> `$DATABASE_URL` and builds a standard engine.

**Frontend** (Vitest):

```bash
cd frontend
npm install
npm test
```

Neither suite runs during a Netlify build (`npm run build` only compiles). To gate
a Render deploy on the backend suite, set the service's **Pre-Deploy Command** to
`cd BackEnd && pytest` — `pytest` and `httpx` are in `BackEnd/requirements.txt`, so
plain `pytest` with nothing installed will fail with `command not found`.

## Adding an input to the deal form

There are three places a user types deal numbers — the Analyze page, the My Deals
card modal, and the Bought Deals card modal. All three render the **same**
component, `frontend/src/components/DealInputsForm.vue`, so the form markup is
written once and the three stay in sync automatically.

To add a new field, work down this list. Steps 1–4 are the frontend, 5–11 the
backend; the same checklist is repeated in the header comment of
`DealInputsForm.vue`.

**Frontend**

1. **`components/DealInputsForm.vue`** — add the `<MoneyInput>` / `<NumberInput>` /
   `<SliderField>` to the right section. Read with `get('field')`, write with
   `set('field', v)`. This is the only UI edit.
2. **`types/index.ts`** — add the field to `BaseDealReq` (shared by both deal
   types) or to `BrrrAnalyzeReq` / `FlipAnalyzeReq` (type-specific).
   `DealInputModel`, `BrrrDealCreate`, `FlipDealCreate` and `AnalyzeDealReq` all
   derive from those, so they need no edit.
3. **`utils/dealUtils.ts`** — add a starting value to `createEmptyDealForm`. If
   it's a BRRRR field with a *server* default, also add it to
   `BRRR_LEGACY_DEFAULTS` so `ensureBrrrLegacyDefaults` backfills deals saved
   before the field existed. Add a line to `formatDealForClipboard` if it should
   appear in the "Copy Summary for AI" text.
4. **`utils/dealUtils.ts`** — add bounds checks to `validateDealInputs`.

**Backend**

5. **`BackEnd/ReqRes/common/analyze_inputs.py`** — add the field to
   `analyzeBRRRReq` and/or `analyzeFlipReq` (the `/analyze/*` endpoints) *and*
   to **`BackEnd/ReqRes/common/active_deal_schemas.py`** (`BaseDealReq`, or
   `BrrrActiveDealCreate` / `FlipActiveDealCreate`). `bought_deal_schemas.py`
   inherits from the active-deal create models — verify rather than
   duplicate. Every division's per-endpoint `ReqRes/<division>/<endpoint>/`
   file just re-exports these — there's nothing to add there.
   **The Pydantic `alias=` must exactly match the field name used in step 1.**
6. **`BackEnd/ReqRes/common/analyze_results.py`** (`analyzeBRRRRes` /
   `analyzeFlipRes`) — only for computed *output* metrics, not raw inputs.
7. **`BackEnd/DAL/data_models/`** — add the `Column` to `common/base_deal.py`'s
   `BaseDeal` mixin (shared) or to **all four** of `activeDeal/deals.py`'s
   `BrrrActiveDeal` / `FlipActiveDeal` and `boughtDeal/deals.py`'s
   `BoughtBrrrDeal` / `BoughtFlipDeal`. The column name is the non-aliased
   snake_case name.
8. **`BackEnd/migrations/runner.py`** — call `add_column_if_missing` for every
   affected existing table (see `migrations/steps/` for the pattern).
   `Base.metadata.create_all` only creates *new* tables, so without this,
   existing rows lack the column. The migration `DEFAULT` must match the
   model `default=` and the Pydantic default, because `update_*_deal` dumps
   every field (no `exclude_unset`) on each PUT.
9. **`BackEnd/BL/common/deal_analysis.py`** / **`deal_validation.py`** — use
   the field in `calculate_brrr_results` / `calculate_flip_results` and
   `validate_brrr_inputs` / `validate_flip_inputs`; register a `CalcStep`
   (see `BL/common/calc_breakdown.py`) if it feeds a headline metric.
10. **`BackEnd/DAL/crud/active_deal.py`** / **`bought_deal.py`** — no change
    expected; they iterate `__table__.columns` dynamically. Confirm only.
11. **`BackEnd/BL/reports/common/deal_pdf.py`** — only if it's a headline
    metric; the PDF renders result metrics and breakdowns, not raw inputs.

**Then**

12. Extend `components/DealInputsForm.test.ts`, run `npm test` and
    `npm run build` (the latter runs `vue-tsc`), and smoke-test all three pages.

> `DealInputsForm` mutates the deal object it is given **in place**. The card
> modals drive auto-save and re-analyze from a deep `watch` on that object, so
> the component deliberately writes through instead of emitting a replacement.
