"""JUnit XML (pytest ``--junitxml``, vitest ``--reporter=junit``) → suite summary.

Standard library only. Tolerates both a ``<testsuites>`` root and a bare
``<testsuite>``. A missing or unparsable file yields ``available: False`` so the
email can say so instead of failing.
"""

from __future__ import annotations

import pathlib
import xml.etree.ElementTree as ET
from collections import defaultdict


def _case_status(case: ET.Element) -> tuple[str, str]:
    for tag, status in (("failure", "failed"), ("error", "error"), ("skipped", "skipped")):
        node = case.find(tag)
        if node is not None:
            message = (node.get("message") or (node.text or "").strip().splitlines()[0:1] or [""])
            return status, (message if isinstance(message, str) else message[0])[:300]
    return "passed", ""


MCP_MODULE_PREFIX = "tests.test_mcp"


def subset(suite: dict, prefix: str = MCP_MODULE_PREFIX) -> dict:
    """The part of a parsed suite whose cases live in modules starting with `prefix`.

    Used to break the MCP server tests (tests/test_mcp*.py) out of the single backend
    JUnit file; any future test_mcp_*.py module is included by construction.
    """
    if not suite.get("available"):
        return dict(suite)
    cases = [c for c in suite["cases"] if c["classname"].startswith(prefix)]
    failed = [c for c in cases if c["status"] in ("failed", "error")]
    return {
        "available": True, "error": "",
        "tests": len(cases),
        "failures": sum(1 for c in cases if c["status"] == "failed"),
        "errors": sum(1 for c in cases if c["status"] == "error"),
        "skipped": sum(1 for c in cases if c["status"] == "skipped"),
        "passed": sum(1 for c in cases if c["status"] == "passed"),
        "time_s": round(sum(c["time_s"] for c in cases), 3),
        "cases": cases,
        "failed": failed,
        "slowest": sorted(cases, key=lambda c: c["time_s"], reverse=True)[:10],
        "by_file": {k: v for k, v in suite["by_file"].items() if k.startswith(prefix)},
    }


def parse(path: pathlib.Path | str | None) -> dict:
    """Return a SuiteSummary dict. ``available`` is False when nothing usable was read."""
    empty = {
        "available": False, "error": "", "tests": 0, "failures": 0, "errors": 0, "skipped": 0,
        "passed": 0, "time_s": 0.0, "cases": [], "failed": [], "slowest": [], "by_file": {},
    }
    if path is None:
        return empty
    path = pathlib.Path(path)
    if not path.exists():
        return {**empty, "error": "artifact missing"}
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError as exc:
        return {**empty, "error": f"unparsable JUnit XML: {exc}"}

    suites = [root] if root.tag == "testsuite" else list(root.iter("testsuite"))
    cases: list[dict] = []
    by_file: dict[str, dict] = defaultdict(lambda: {"tests": 0, "failed": 0, "skipped": 0, "time_s": 0.0})
    for suite in suites:
        for case in suite.iter("testcase"):
            status, message = _case_status(case)
            time_s = float(case.get("time") or 0.0)
            classname = case.get("classname") or case.get("file") or suite.get("name") or ""
            record = {
                "classname": classname,
                "name": case.get("name") or "",
                "time_s": time_s,
                "status": status,
                "message": message,
            }
            cases.append(record)
            bucket = by_file[classname]
            bucket["tests"] += 1
            bucket["time_s"] += time_s
            if status in ("failed", "error"):
                bucket["failed"] += 1
            if status == "skipped":
                bucket["skipped"] += 1

    if not cases:
        return {**empty, "error": "no test cases in the JUnit XML"}

    failures = sum(1 for c in cases if c["status"] == "failed")
    errors = sum(1 for c in cases if c["status"] == "error")
    skipped = sum(1 for c in cases if c["status"] == "skipped")
    # Prefer the reporter's own wall time when it is on the root; else sum the cases.
    time_attr = root.get("time") or (suites[0].get("time") if len(suites) == 1 else None)
    time_s = float(time_attr) if time_attr else sum(c["time_s"] for c in cases)
    return {
        "available": True,
        "error": "",
        "tests": len(cases),
        "failures": failures,
        "errors": errors,
        "skipped": skipped,
        "passed": len(cases) - failures - errors - skipped,
        "time_s": time_s,
        "cases": cases,
        "failed": [c for c in cases if c["status"] in ("failed", "error")],
        "slowest": sorted(cases, key=lambda c: -c["time_s"])[:10],
        "by_file": dict(sorted(by_file.items(), key=lambda kv: -kv[1]["time_s"])),
    }


def case_label(case: dict) -> str:
    return f"{case['classname']}::{case['name']}" if case["classname"] else case["name"]
