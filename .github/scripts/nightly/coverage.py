"""Coverage summaries → lowest-covered modules.

Reads pytest-cov's ``--cov-report=json`` file and vitest's ``json-summary``
reporter file. When neither is present the email prints the wiring steps.
"""

from __future__ import annotations

import json
import pathlib

MIN_STATEMENTS = 10  # ignore trivial files when ranking the lowest-covered modules

NOT_WIRED_STEPS = [
    "Backend: add `pytest-cov>=5.0` to BackEnd/requirements.txt and run pytest with "
    "`--cov=. --cov-config=../.github/nightly/coveragerc --cov-report=json:<path>`.",
    "Frontend: `npm i -D --save-exact @vitest/coverage-v8@4.1.4` and run vitest with "
    "`--coverage.enabled --coverage.provider=v8 --coverage.reporter=json-summary`.",
    "Upload both JSON files from the CI jobs and pass them to the email with "
    "`--backend-coverage` / `--frontend-coverage`.",
]


def _empty(error: str = "") -> dict:
    return {"available": False, "error": error, "pct": None, "files": [], "lowest": []}


def _finish(pct: float | None, files: list[tuple[str, float, int]]) -> dict:
    ranked = sorted((f for f in files if f[2] >= MIN_STATEMENTS), key=lambda f: (f[1], -f[2]))
    return {"available": True, "error": "", "pct": pct, "files": files, "lowest": ranked[:5]}


def parse_pytest_cov_json(path: pathlib.Path | str | None) -> dict:
    """pytest-cov / coverage.py JSON: ``totals.percent_covered`` and per-file summaries."""
    if path is None:
        return _empty()
    path = pathlib.Path(path)
    if not path.exists():
        return _empty("artifact missing")
    try:
        data = json.loads(path.read_text())
    except ValueError as exc:
        return _empty(f"unparsable coverage JSON: {exc}")
    files = []
    for name, entry in (data.get("files") or {}).items():
        summary = entry.get("summary") or {}
        files.append((name.replace("\\", "/"), float(summary.get("percent_covered", 0.0)), int(summary.get("num_statements", 0))))
    totals = data.get("totals") or {}
    pct = totals.get("percent_covered")
    return _finish(float(pct) if pct is not None else None, files)


def parse_vitest_summary(path: pathlib.Path | str | None, strip_prefix: str = "") -> dict:
    """vitest ``json-summary``: ``total.lines.pct`` and per-file ``lines``."""
    if path is None:
        return _empty()
    path = pathlib.Path(path)
    if not path.exists():
        return _empty("artifact missing")
    try:
        data = json.loads(path.read_text())
    except ValueError as exc:
        return _empty(f"unparsable coverage summary: {exc}")
    files = []
    for name, entry in data.items():
        if name == "total":
            continue
        lines = entry.get("lines") or {}
        rel = name.replace("\\", "/")
        marker = rel.find("/frontend/")
        if marker != -1:
            rel = rel[marker + len("/frontend/"):]
        elif strip_prefix and rel.startswith(strip_prefix):
            rel = rel[len(strip_prefix):]
        files.append((rel, float(lines.get("pct", 0.0)), int(lines.get("total", 0))))
    pct = ((data.get("total") or {}).get("lines") or {}).get("pct")
    return _finish(float(pct) if pct is not None else None, files)


def status(backend: dict, frontend: dict) -> str:
    """'wired' when both summaries exist, 'partial' for one, else 'not_wired'."""
    present = sum(1 for c in (backend, frontend) if c.get("available"))
    return {2: "wired", 1: "partial", 0: "not_wired"}[present]
