"""Playwright JSON reporter output → flat, keyed test records.

Keys follow ``frontend/e2e/scripts/compare-reports.mjs`` exactly
(``project :: file :: title`` with the file made repo-relative), so anything
recorded in history stays comparable with that script's output.
"""

from __future__ import annotations

import json
import pathlib
import re
from collections import defaultdict

TOP_N = 17

STATUS_LABELS = {
    "expected": "passed",
    "unexpected": "failed",
    "flaky": "flaky",
    "skipped": "skipped",
}

_ABSOLUTE = re.compile(r"^(/|[A-Za-z]:/)")


def normalize_file(file: str | None, root_dir: str = "") -> str:
    """Port of ``normalizeFile`` in compare-reports.mjs. Never returns an absolute path."""
    if not file:
        return ""
    path = str(file).replace("\\", "/")
    root = str(root_dir or "").replace("\\", "/").rstrip("/")
    if root and path.startswith(root + "/"):
        return path[len(root) + 1:]
    if not _ABSOLUTE.match(path):
        return path[2:] if path.startswith("./") else path
    marker = path.rfind("/e2e/")
    if marker != -1:
        return path[marker + len("/e2e/"):]
    return path[path.rfind("/") + 1:]


def test_key(project: str, file: str, title: str) -> str:
    return f"{project} :: {file} :: {title}"


def walk_tests(suite: dict, chain: list[str], out: list[dict], root_dir: str = "") -> None:
    """Flatten Playwright's nested suites into one record per test."""
    for spec in suite.get("specs", []):
        parts = [p for p in chain if p] + [spec.get("title", "")]
        title = " > ".join(p for p in parts if p)
        file_raw = spec.get("file", "")
        file_rel = normalize_file(file_raw, root_dir)
        for test in spec.get("tests", []):
            results = test.get("results", [])
            annotations = list(test.get("annotations", []) or [])
            for r in results:
                for a in r.get("annotations", []) or []:
                    if a not in annotations:
                        annotations.append(a)
            skip_reasons = [a.get("description") or "" for a in annotations if a.get("type") == "skip"]
            project = test.get("projectName", "?")
            out.append({
                "project": project,
                "status": test.get("status", "?"),
                "file": file_raw,
                "file_rel": file_rel,
                "title": title,
                "key": test_key(project, file_rel, title),
                "calls": len(results),
                "reruns": sum(1 for r in results if r.get("retry", 0) > 0),
                "duration_ms": max((r.get("duration", 0) for r in results), default=0),
                "annotations": annotations,
                "skip_reasons": skip_reasons,
            })
    for child in suite.get("suites", []):
        # A file-level suite's title is the file path; drop it from the chain.
        title = child.get("title", "")
        next_chain = chain + ([] if title == child.get("file") or title.endswith(".ts") else [title])
        walk_tests(child, next_chain, out, root_dir)


def load_report(path: pathlib.Path | str | None) -> dict | None:
    if path is None:
        return None
    path = pathlib.Path(path)
    if not path.exists():
        return None
    return json.loads(path.read_text())


def empty_summary() -> dict:
    return {
        "available": False,
        "tests": [],
        "passed": 0, "failed": 0, "skipped": 0, "flaky": 0,
        "total_calls": 0, "rerun_tests": 0, "duration_ms": 0,
        "per_project": {}, "failed_tests": [], "top": [],
        "tests_by_key": {}, "flaky_tests": [], "spec_file_ms": {},
        "projects_present": [], "start_time": "",
    }


def summarise(report: dict | None) -> dict:
    """Everything the template shows, computed once. Every legacy field is kept."""
    if report is None:
        return empty_summary()

    root_dir = (report.get("config") or {}).get("rootDir", "")
    tests: list[dict] = []
    for suite in report.get("suites", []):
        walk_tests(suite, [], tests, root_dir)

    stats = report.get("stats", {})
    per_project: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    spec_file_ms: dict[str, float] = defaultdict(float)
    for t in tests:
        per_project[t["project"]][t["status"]] += 1
        if t["status"] != "skipped":  # a skip's few ms are bookkeeping, not runtime
            spec_file_ms[t["file_rel"]] += t["duration_ms"]

    return {
        "available": True,
        "tests": tests,
        "passed": stats.get("expected", 0),
        "failed": stats.get("unexpected", 0),
        "skipped": stats.get("skipped", 0),
        "flaky": stats.get("flaky", 0),
        "total_calls": sum(t["calls"] for t in tests),
        "rerun_tests": sum(1 for t in tests if t["reruns"]),
        "duration_ms": stats.get("duration", 0),
        "per_project": {k: dict(v) for k, v in sorted(per_project.items())},
        "failed_tests": [t for t in tests if t["status"] == "unexpected"],
        "top": sorted(tests, key=lambda t: t["duration_ms"], reverse=True)[:TOP_N],
        "tests_by_key": {t["key"]: t for t in tests},
        "flaky_tests": [t for t in tests if t["status"] == "flaky"],
        "spec_file_ms": dict(sorted(spec_file_ms.items(), key=lambda kv: -kv[1])),
        "projects_present": sorted(per_project),
        "start_time": stats.get("startTime", ""),
    }


def test_label(t: dict) -> str:
    return f"{t['file_rel'] or t['file']}::{t['title']}"
