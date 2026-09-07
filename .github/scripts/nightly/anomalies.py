"""Cross-source rules: deltas, failure classes, flaky tests, duration regressions, coverage drops.

Baselines are prior nightly records with the same Playwright matrix (see
``history.comparable``). Every finding is ``{id, severity, title, detail, section}``.
"""

from __future__ import annotations

import statistics

SLOW_FACTOR = 1.5          # D1: tonight > 1.5 × median of the last 7
SLOW_MIN_SAMPLES = 3
SLOW_MIN_DELTA_MS = 2000
WALL_FACTOR = 1.3          # D2
FILE_TREND_BAND = 0.15     # D3: ±15 % counts as steady
COVERAGE_DROP_PTS = 1.0    # C1
FIRST_SEEN_WINDOW = 30
FLIP_WINDOW = 7


def delta(current: float | int | None, baseline: float | int | None) -> dict | None:
    """Signed difference with a word, or None when either side is missing."""
    if current is None or baseline is None:
        return None
    diff = current - baseline
    if diff == 0:
        word = "no change"
    else:
        word = f"{'up' if diff > 0 else 'down'} {abs(diff):g}"
    return {"diff": diff, "word": word}


SUITES = ("playwright", "backend", "frontend")


def suite_totals(record: dict) -> dict:
    """Passed / failed / skipped / total across every suite in a record, plus the per-suite parts.

    Playwright counts come from its stats (a flaky test passed on retry, so it counts as passed);
    pytest and vitest from their JUnit summaries. A suite whose report is missing contributes
    nothing and is marked ``available: False`` in ``parts``.
    """
    parts: dict[str, dict] = {}
    pw = record.get("playwright") or {}
    stats = pw.get("stats") or {}
    if pw.get("available", bool(stats)):
        passed = stats.get("expected", 0) + stats.get("flaky", 0)
        parts["playwright"] = {"available": True, "passed": passed, "failed": stats.get("unexpected", 0),
                               "skipped": stats.get("skipped", 0)}
    else:
        parts["playwright"] = {"available": False}
    for name in ("backend", "frontend"):
        j = ((record.get("junit") or {}).get(name)) or {}
        if j.get("available"):
            failed = j.get("failures", 0) + j.get("errors", 0)
            parts[name] = {"available": True, "passed": j.get("tests", 0) - failed - j.get("skipped", 0),
                           "failed": failed, "skipped": j.get("skipped", 0)}
        else:
            parts[name] = {"available": False}
    for part in parts.values():
        if part["available"]:
            part["total"] = part["passed"] + part["failed"] + part["skipped"]
    totals = {k: sum(p[k] for p in parts.values() if p["available"]) for k in ("passed", "failed", "skipped", "total")}
    totals["parts"] = parts
    return totals


def tile_deltas(record: dict, prev: dict | None, week: dict | None) -> dict:
    """Tile deltas over the combined totals of every suite (see ``suite_totals``)."""
    cur = suite_totals(record)
    prev_t = suite_totals(prev) if prev else None
    week_t = suite_totals(week) if week else None
    out = {}
    for tile in ("passed", "failed", "skipped", "total"):
        out[tile] = {
            "vs_prev": delta(cur[tile], prev_t[tile]) if prev_t else None,
            "vs_week": delta(cur[tile], week_t[tile]) if week_t else None,
        }
    return out


def failure_classes(record: dict, prior: list[dict]) -> dict[str, dict]:
    """Per failed key: first_seen (never failed in the window) or recurring (k of last N)."""
    failed_now = (record.get("playwright") or {}).get("failed") or []
    window = prior[-FIRST_SEEN_WINDOW:]
    out = {}
    for key in failed_now:
        count = sum(1 for r in window if key in set(((r.get("playwright") or {}).get("failed") or []))
                    or key in set(((r.get("playwright") or {}).get("flaky") or [])))
        out[key] = {"first_seen": count == 0, "recurring": count, "window": len(window)}
    return out


def flaky_tests(record: dict, prior: list[dict]) -> list[dict]:
    """Playwright-flaky tonight, or ≥2 pass↔fail flips over the last 7 records."""
    pw = record.get("playwright") or {}
    result = [{"key": k, "why": "flaky tonight (passed on retry)"} for k in pw.get("flaky") or []]
    recent = prior[-FLIP_WINDOW:] + [record]
    keys = set()
    for r in recent:
        p = r.get("playwright") or {}
        keys |= set(p.get("failed") or []) | set(p.get("flaky") or [])
    for key in sorted(keys):
        states = []
        for r in recent:
            p = r.get("playwright") or {}
            if key in (p.get("failed") or []) or key in (p.get("flaky") or []):
                states.append("bad")
            elif key in (p.get("durations") or {}):
                states.append("ok")
        flips = sum(1 for a, b in zip(states, states[1:]) if a != b)
        if flips >= 2 and not any(f["key"] == key for f in result):
            result.append({"key": key, "why": f"{flips} pass/fail flips in the last {len(recent)} runs"})
    return result


def _median_duration(key: str, prior: list[dict]) -> tuple[float | None, int]:
    values = [float((r.get("playwright") or {}).get("durations", {}).get(key)) for r in prior[-7:]
              if (r.get("playwright") or {}).get("durations", {}).get(key) is not None]
    return (statistics.median(values) if values else None), len(values)


def slow_regressions(record: dict, prior: list[dict]) -> dict[str, dict]:
    """D1 per key: {median_ms, ratio} for tests slower than usual."""
    out = {}
    for key, ms in ((record.get("playwright") or {}).get("durations") or {}).items():
        median, n = _median_duration(key, prior)
        if median is None or n < SLOW_MIN_SAMPLES or median <= 0:
            continue
        if ms > SLOW_FACTOR * median and ms - median >= SLOW_MIN_DELTA_MS:
            out[key] = {"median_ms": median, "ratio": ms / median, "samples": n}
    return out


def wall_clock(record: dict, prior: list[dict]) -> dict | None:
    cur = ((record.get("playwright") or {}).get("stats") or {}).get("duration_ms")
    values = [((r.get("playwright") or {}).get("stats") or {}).get("duration_ms") for r in prior[-7:]]
    values = [v for v in values if v]
    if not cur or len(values) < SLOW_MIN_SAMPLES:
        return None
    median = statistics.median(values)
    return {"median_ms": median, "ratio": cur / median, "slow": cur > WALL_FACTOR * median}


def spec_file_trend(record: dict, prior: list[dict], top: int = 8) -> list[dict]:
    files = (record.get("playwright") or {}).get("spec_files") or {}
    rows = []
    for file, ms in sorted(files.items(), key=lambda kv: -kv[1])[:top]:
        values = [((r.get("playwright") or {}).get("spec_files") or {}).get(file) for r in prior[-7:]]
        values = [v for v in values if v]
        if len(values) >= SLOW_MIN_SAMPLES:
            median = statistics.median(values)
            ratio = ms / median if median else 1.0
            arrow = "up" if ratio > 1 + FILE_TREND_BAND else ("down" if ratio < 1 - FILE_TREND_BAND else "steady")
        else:
            median, ratio, arrow = None, None, "no history"
        rows.append({"file": file, "ms": ms, "median_ms": median, "ratio": ratio, "trend": arrow})
    return rows


def suite_findings(name: str, junit: dict, prev: dict | None) -> list[dict]:
    """J1 failures, J2 skipped-count change."""
    if not junit.get("available"):
        return []
    out = []
    if junit["failures"] or junit["errors"]:
        names = ", ".join(f"{c['classname']}::{c['name']}" for c in junit["failed"][:5])
        out.append({"id": "J1", "severity": "critical", "section": "Backend and frontend suites",
                    "title": f"{name}: {junit['failures'] + junit['errors']} failing test(s)",
                    "detail": names + (" …" if len(junit["failed"]) > 5 else "")})
    prev_part = ((prev or {}).get("junit") or {}).get(name.lower()) or {}
    if prev_part.get("available") and prev_part.get("skipped") != junit["skipped"]:
        out.append({"id": "J2", "severity": "notice", "section": "Backend and frontend suites",
                    "title": f"{name}: skipped count changed",
                    "detail": f"{prev_part.get('skipped')} last run, {junit['skipped']} tonight."})
    return out


def coverage_findings(name: str, cov: dict, prev: dict | None) -> list[dict]:
    if not cov.get("available") or cov.get("pct") is None:
        return []
    prev_pct = (((prev or {}).get("coverage") or {}).get(name.lower()) or {}).get("pct")
    if prev_pct is not None and prev_pct - cov["pct"] > COVERAGE_DROP_PTS:
        return [{"id": "C1", "severity": "warning", "section": "Coverage gaps",
                 "title": f"{name} line coverage dropped",
                 "detail": f"{prev_pct:.1f}% last run, {cov['pct']:.1f}% tonight."}]
    return []


def collect(record: dict, prior: list[dict], prev: dict | None, skip_anomalies: list[dict],
            backend: dict, frontend: dict, cov_backend: dict, cov_frontend: dict,
            history_error: str, malformed: int, allowlist_error: str) -> dict:
    """Run every rule and return the analysis bundle the renderers consume."""
    findings: list[dict] = list(skip_anomalies)
    classes = failure_classes(record, prior)
    for key, info in classes.items():
        if info["first_seen"]:
            findings.append({"id": "F1", "severity": "critical", "section": "Failed tests",
                             "title": "First-time failure", "detail": key})
        else:
            findings.append({"id": "F1", "severity": "warning", "section": "Failed tests",
                             "title": f"Recurring failure ({info['recurring']} of the last {info['window']} runs)",
                             "detail": key})
    flaky = flaky_tests(record, prior)
    for f in flaky:
        findings.append({"id": "F2", "severity": "warning", "section": "Failed tests",
                         "title": "Flaky test", "detail": f"{f['key']} ({f['why']})"})
    slow = slow_regressions(record, prior)
    for key, info in slow.items():
        findings.append({"id": "D1", "severity": "warning", "section": "Top longest-running tests",
                         "title": "Slower than usual",
                         "detail": f"{key}: {info['ratio']:.1f}× its 7-run median ({info['median_ms'] / 1000:.1f}s)"})
    wall = wall_clock(record, prior)
    if wall and wall["slow"]:
        findings.append({"id": "D2", "severity": "notice", "section": "Test session report",
                         "title": "Playwright wall-clock above its recent median",
                         "detail": f"{wall['ratio']:.2f}× the 7-run median of {wall['median_ms'] / 60000:.1f} min."})
    findings += suite_findings("Backend", backend, prev) + suite_findings("Frontend", frontend, prev)
    findings += coverage_findings("Backend", cov_backend, prev) + coverage_findings("Frontend", cov_frontend, prev)
    if malformed:
        findings.append({"id": "H1", "severity": "notice", "section": "Trends",
                         "title": f"{malformed} unreadable history line(s) were skipped", "detail": history_error or ""})
    if allowlist_error:
        findings.append({"id": "H1", "severity": "notice", "section": "Skipped by reason",
                         "title": "Skip allow-list unavailable", "detail": allowlist_error})
    order = {"critical": 0, "warning": 1, "notice": 2}
    findings.sort(key=lambda a: (order[a["severity"]], a["id"], a["title"]))
    return {
        "findings": findings,
        "failure_classes": classes,
        "flaky": flaky,
        "slow": slow,
        "wall": wall,
        "spec_files": spec_file_trend(record, prior),
        "deltas": None,  # filled by main once prev/week are known
    }
