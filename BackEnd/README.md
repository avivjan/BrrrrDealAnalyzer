## BrrrrDealAnalyzer FastAPI Example

This is a minimal FastAPI application exposing a few endpoints: `helloworld`, `analyzeDeal`, and active deal management routes.

### Install dependencies

```bash
cd /Users/avivjan/git/BrrrrDealAnalyzer
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Run the app

```bash
uvicorn main:app --reload
```

The app will start by default on `http://127.0.0.1:8000`.

### Endpoint

- **GET** `/helloworld`
  Returns a JSON object: `{"message": "Hello, World!"}`.
- **POST** `/analyzeDeal`
  Accepts the payload defined in `ReqRes/analyzeDeal/analyzeDealReq.py` and returns deal metrics.
- **POST** `/active-deals`
  Persists an active deal using the `DATABASE_URL` PostgreSQL connection (Render-compatible). Requires a JSON body matching `ReqRes/activeDeal/activeDealReq.ActiveDealCreate`.
- **GET** `/active-deals`
  Returns all stored active deals ordered by most recent creation time.

### Database setup

The app expects a `DATABASE_URL` environment variable pointing to a PostgreSQL instance (as provided by Render). On startup, `main.py` will create the `active_deals` table if it does not exist:

```bash
export DATABASE_URL=postgresql://<username>:<password>@<host>:<port>/<database>
uvicorn main:app --reload
```


