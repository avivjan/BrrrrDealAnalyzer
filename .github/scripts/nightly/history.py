"""One compact JSON record per nightly run, appended to ``history.jsonl``.

The file lives on the orphan branch ``nightly-history``; the workflow checks it
out as a worktree, this module reads the tail and appends tonight's record, and
the workflow pushes it back. Records carry only repo-relative paths.
"""

from __future__ import annotations

import datetime as dt
import json
import pathlib

RECORD_VERSION = 1
DURATIONS_KEPT = 25


def load_tail(path: pathlib.Path | str | None, window: int = 30) -> tuple[list[dict], int]:
    """Return (records, malformed_line_count) for the last ``window`` v1 records."""
    if path is None:
        return [], 0
    path = pathlib.Path(path)
    if not path.exists():
        return [], 0
    records: list[dict] = []
    malformed = 0
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except ValueError:
            malformed += 1
            continue
        if isinstance(rec, dict) and rec.get("v") == RECORD_VERSION:
            records.append(rec)
        else:
            malformed += 1
    records.sort(key=lambda r: (r.get("run") or {}).get("started") or "")
    return records[-window:], malformed


def append(path: pathlib.Path | str, record: dict) -> None:
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, separators=(",", ":"), sort_keys=True) + "\n")


def write_record(path: pathlib.Path | str, record: dict) -> None:
    pathlib.Path(path).write_text(json.dumps(record, separators=(",", ":"), sort_keys=True) + "\n")


def nightly_only(records: list[dict]) -> list[dict]:
    return [r for r in records if r.get("source", "nightly") == "nightly"]


def same_matrix(a: dict, b: dict) -> bool:
    pa = set(((a.get("playwright") or {}).get("projects") or {}).keys())
    pb = set(((b.get("playwright") or {}).get("projects") or {}).keys())
    return bool(pa) and pa == pb


def comparable(prior: list[dict], record: dict) -> list[dict]:
    """Prior nightly records whose Playwright matrix matches tonight's."""
    return [r for r in nightly_only(prior) if same_matrix(r, record)]


def previous(prior: list[dict], record: dict) -> dict | None:
    comp = comparable(prior, record)
    return comp[-1] if comp else None


def week_ago(prior: list[dict], record: dict, now: dt.datetime) -> dict | None:
    cutoff = (now - dt.timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")
    candidates = [r for r in comparable(prior, record) if (r.get("run") or {}).get("started", "") <= cutoff]
    return candidates[-1] if candidates else None


def build_record(*, run: dict, verdict: str, jobs: dict, summary: dict, skips_record: dict,
                 backend: dict, frontend: dict, coverage_backend: dict, coverage_frontend: dict,
                 prior: list[dict]) -> dict:
    tests = summary.get("tests", [])
    # Durations: tonight's top 25 plus every key the previous record tracked, so medians stay computable.
    carry = set(((prior[-1].get("playwright") or {}).get("durations") or {}).keys()) if prior else set()
    ranked = sorted((t for t in tests if t["status"] != "skipped"), key=lambda t: -t["duration_ms"])
    keep = {t["key"] for t in ranked[:DURATIONS_KEPT]} | carry
    durations = {t["key"]: round(t["duration_ms"]) for t in tests if t["key"] in keep and t["status"] != "skipped"}

    projects = {}
    for project, counts in (summary.get("per_project") or {}).items():
        projects[project] = {k: v for k, v in counts.items()}

    def junit_part(s: dict) -> dict:
        if not s.get("available"):
            return {"available": False}
        return {
            "available": True,
            "tests": s["tests"], "failures": s["failures"], "errors": s["errors"], "skipped": s["skipped"],
            "time_s": round(s["time_s"], 2),
            "failed": [f"{c['classname']}::{c['name']}" for c in s["failed"]][:40],
            "slowest": [[f"{c['classname']}::{c['name']}", round(c["time_s"], 3)] for c in s["slowest"]],
        }

    def cov_part(c: dict) -> dict | None:
        if not c.get("available"):
            return None
        return {"pct": round(c["pct"], 2) if c["pct"] is not None else None,
                "lowest": [[p, round(pct, 1), n] for p, pct, n in c["lowest"]]}

    return {
        "v": RECORD_VERSION,
        "source": "nightly",
        "run": run,
        "verdict": verdict,
        "jobs": jobs,
        "playwright": {
            "available": bool(summary.get("available")),
            "stats": {
                "expected": summary.get("passed", 0), "unexpected": summary.get("failed", 0),
                "flaky": summary.get("flaky", 0), "skipped": summary.get("skipped", 0),
                "duration_ms": round(summary.get("duration_ms", 0)),
            },
            "projects": projects,
            "skips": skips_record,
            "failed": [t["key"] for t in summary.get("failed_tests", [])],
            "flaky": [t["key"] for t in summary.get("flaky_tests", [])],
            "skipped_keys": [t["key"] for t in tests if t["status"] == "skipped"],
            "durations": durations,
            "spec_files": {f: round(ms) for f, ms in (summary.get("spec_file_ms") or {}).items()},
        },
        "junit": {"backend": junit_part(backend), "frontend": junit_part(frontend)},
        "coverage": {"backend": cov_part(coverage_backend), "frontend": cov_part(coverage_frontend)},
    }
