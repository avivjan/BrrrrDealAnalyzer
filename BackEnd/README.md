## BrrrrDealAnalyzer Backend

A FastAPI backend for underwriting and tracking BRRRR / Flip real-estate deals,
plus a liquidity timeline and a REPS (Real Estate Professional Status) time
tracker. Persistence is PostgreSQL in production (Render) and a throwaway PostgreSQL container in tests.

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
    analyzeBRRR.py    #   analyze_brrr() + calculate_brrr_results() + compute_brrr()
    analyzeFlip.py    #   analyze_flip() + calculate_flip_results() + compute_flip()
    brrr_calc.py      #   BrrrCalc / FlipCalc: the frozen record of every number
    flip_calc.py      #   the calculation produces
    brrrSteps/        #   one pure step per calculation subject (cash_flow, dscr,
    flipSteps/        #   roi, total_cash_needed, ...)
    explain/          #   the breakdown narrative, built from the record and
                      #   guarded against it (brrr.py, flip.py)
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
calculation, in two layers. `compute_brrr()` / `compute_flip()` are the pure
engine: the orchestrator reads top-to-bottom as the calculation itself, each
line calls one pure `*_step` from `brrrSteps/` / `flipSteps/`, and the result
is a frozen `BrrrCalc` / `FlipCalc` record of every number produced. The
narrative behind those numbers lives in `explain/`, which reads the record,
never recomputes, and guards every equation it states (`check` / `add_sum`),
so a math change that is not mirrored in the text raises instead of printing
a stale formula; `tests/test_explain.py` fails if a record field is never
explained. `calculate_*_results()` is engine + explanation as the response
model, and `analyze_*()` validates first.

### Tests

```bash
docker compose -f docker-compose.test.yml up -d --wait   # throwaway Postgres on 127.0.0.1:55432
python3 -m pytest
docker compose -f docker-compose.test.yml down           # when done; the data lives on tmpfs
```

`tests/conftest.py` never reads `DATABASE_URL`: it overwrites it with
`TEST_DATABASE_URL` (default: the compose container above) and stubs `dotenv`
before importing the app, then verifies -- at import, at session start and
before every test -- that the engine is PostgreSQL on a loopback host with a
`_test` database, aborting otherwise. Only then is the schema dropped and
recreated for the session. See the module docstring there for the full
isolation design. In CI the same suite runs against the backend job's
`postgres:16` service container.
Neither this suite nor the frontend's runs during a Netlify build (`npm run
build` only compiles). To gate a Render deploy on it, set the service's
**Pre-Deploy Command** to `cd BackEnd && pytest`.

### Regression harness

`verify_regression.py` is a standalone script (not part of `pytest`) that
snapshots the full observable contract -- the OpenAPI schema, every ORM
table/column, Pydantic model behavior, calculation results to the last decimal
place, and a scripted pass through all 45 endpoints -- and asserts bit-for-bit
identity on replay. It was built to guard the router/BL/DAL layering
refactor; re-run it after any change that could shift behavior. It uses the
same throwaway test PostgreSQL as `pytest` (start it first, see Tests above)
and the same isolation guard, `tests/db_isolation_guard.py`:

```bash
python3 verify_regression.py verify      # compare against tests/_regression_snapshots/
python3 verify_regression.py snapshot    # re-record the goldens (review the diff!)
```

### Adding an input to the deal form

See the root [`README.md`](../README.md) for the full checklist (frontend
form → `types/` → `ReqRes/common/` alias → `DAL/data_models/` column →
`migrations/` backfill → `DAL/crud/` → PDF report).
