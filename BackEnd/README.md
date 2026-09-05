## BrrrrDealAnalyzer Backend

A FastAPI backend for underwriting and tracking BRRRR / Flip real-estate deals,
plus a liquidity timeline and a REPS (Real Estate Professional Status) time
tracker. Persistence is PostgreSQL in production (Render) and SQLite in tests.

### Install dependencies

```bash
cd BackEnd
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Run the app

```bash
export DATABASE_URL=postgresql://<username>:<password>@<host>:<port>/<database>
# or, locally: export DATABASE_URL=sqlite:///./dev.db
uvicorn main:app --reload
```

The app starts by default on `http://127.0.0.1:8000`; interactive docs are at
`/docs`. On import, `main.py` runs `bootstrap.run(...)`, which creates any
missing tables, runs the idempotent schema migrations in `migrations/`, and
seeds the default pipeline templates + REPS activity categories.

### Layout

Four layers, each with one direction of dependency:
`routers/` (HTTP) → `BL/` (business logic) → `DAL/` (persistence) → the
database. Every layer is grouped into the same nine endpoint divisions:
`analyze`, `reports`, `activeDeal`, `boughtDeal`, `email`, `liquidity`,
`pipelineTemplate`, `reps`, `health`.

```
main.py            # ~35 lines: app + bootstrap + CORS + mount every router
db.py               # engine / SessionLocal / Base / get_db
bootstrap.py        # schema bootstrap + seed data, run once at import
migrations/         # hand-rolled, idempotent schema migrations (no Alembic)

routers/            # HTTP only: path, method, status codes, exception mapping.
                     # Each endpoint function is a one-liner delegating to BL.
BL/                 # Framework-agnostic business logic. Takes/returns plain
  <division>/         # Python types, Pydantic models, or a DB Session -- never
    <endpoint>.py     # a FastAPI Request/Response. One flat module per
    common/           # endpoint, plus common/ for what that division shares.
  analyze/            # The calc engine -- the core of the product:
    analyzeBRRR.py    #   analyze_brrr()  + calculate_brrr_results()
    analyzeFlip.py    #   analyze_flip()  + calculate_flip_results()
    brrrSteps/        #   one file per calculation subject (cash_flow, dscr,
    flipSteps/        #   roi, total_cash_needed, ...)
    common/           #   deal_math, calc_breakdown, validation
  common/             # deal_response: ORM row -> *Res, shared by the
                     # activeDeal and boughtDeal divisions.
DAL/
  data_models/       # SQLAlchemy ORM tables, grouped by division
  crud/              # Query functions only (add/filter/first/delete) -- no
                     # business logic, no Pydantic construction, no commits
                     # (routers' BL callers own the transaction boundary).

ReqRes/
  common/            # Every Pydantic request/response model, defined once.
  <division>/<endpoint>/   # Thin re-export modules (<name>Req.py / <name>Res.py)
                           # so routers only ever import from ReqRes/.
```

Within `BL/`, a division folder holds one flat module per endpoint
(`BL/liquidity/createRecurring.py`) plus a `common/` subfolder for logic shared
across that division's endpoints. `ReqRes/` still nests one folder per endpoint
(`ReqRes/liquidity/createRecurring/`), holding the two thin re-export modules.

`BL/analyze/` is the exception worth knowing: it holds the whole BRRRR/Flip
calculation. `analyzeBRRR.py` and `analyzeFlip.py` each carry both the
validate-then-calculate entry point and the orchestrator underneath it, and the
orchestrator reads top-to-bottom as the calculation itself -- each line calls
one `*_step` from `brrrSteps/` / `flipSteps/`, where a step does its slice of
the math *and* registers its own `breakdown.add()` lines, so the explanation
the frontend renders travels with the code that computes the value.

### Tests

```bash
cd BackEnd
python3 -m pytest
```

`tests/conftest.py` redirects `DATABASE_URL` to a throwaway SQLite file (and
stubs `dotenv`) before importing the app, so the suite can never touch a real
database -- see the module docstring there for the full isolation design.
Neither this suite nor the frontend's runs during a Netlify build (`npm run
build` only compiles). To gate a Render deploy on it, set the service's
**Pre-Deploy Command** to `cd BackEnd && pytest`.

### Regression harness

`verify_regression.py` is a standalone script (not part of `pytest`) that
snapshots the full observable contract -- the OpenAPI schema, every ORM
table/column, Pydantic model behavior, calculation results to the last decimal
place, and a scripted pass through all 45 endpoints -- and asserts bit-for-bit
identity on replay. It was built to guard the router/BL/DAL layering
refactor; re-run it after any change that could shift behavior:

```bash
python3 verify_regression.py verify
```

### Adding an input to the deal form

See the root [`README.md`](../README.md) for the full checklist (frontend
form → `types/` → `ReqRes/common/` alias → `DAL/data_models/` column →
`migrations/` backfill → `DAL/crud/` → PDF report).
