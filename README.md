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
