## BrrrrDealAnalyzer FastAPI Example

This is a minimal FastAPI application exposing a single endpoint: `helloworld`.

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


