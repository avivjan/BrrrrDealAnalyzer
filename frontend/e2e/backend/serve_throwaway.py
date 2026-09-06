"""Serve the real FastAPI app against a throwaway SQLite database.

Playwright's `webServer` starts this; every e2e run therefore talks to the
*actual* backend, not a mock — the whole point of a network-contract golden.

Nothing here touches `BackEnd/`. The isolation is entirely `verify_regression`'s
doing: importing it (module-level code, its CLI is behind `if __name__ ==
"__main__"`) redirects `DATABASE_URL` at a fresh temp SQLite file, stubs
`load_dotenv`, scrubs every Google / Mercury / SMTP credential so the
integration endpoints take their deterministic "not configured" branch, and
installs the SQLite UUID bind shim. See `BackEnd/verify_regression.py` §2-3.

`sys.dont_write_bytecode` is set before any backend import on purpose:
`BackEnd/__pycache__/main.cpython-311.pyc` is a *tracked* file, and importing
`main` would otherwise rewrite it and dirty the working tree.
"""

import sys

sys.dont_write_bytecode = True  # must precede every backend import

import logging
import pathlib

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
BACKEND_DIR = REPO_ROOT / "BackEnd"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# Order matters: this must run before `main` is imported.
import verify_regression  # noqa: E402,F401  (imported for its side effects)

import main  # noqa: E402
import uvicorn  # noqa: E402

# `main` configures INFO logging on import and the suite deliberately walks
# error paths; keep the Playwright output readable.
logging.getLogger().setLevel(logging.WARNING)

if __name__ == "__main__":
    print(f"e2e backend: DATABASE_URL={verify_regression.TEST_DATABASE_URL}", flush=True)
    uvicorn.run(main.app, host="127.0.0.1", port=8011, log_level="warning")
