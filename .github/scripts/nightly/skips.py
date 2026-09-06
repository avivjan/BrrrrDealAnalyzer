"""Group skipped Playwright tests by their recorded reason and judge them against the allow-list.

Rules (each yields an anomaly dict ``{id, severity, title, detail, section}``):

  S1  a skip reason that matches no allow-list entry                      critical
  S2  a skipped test with no ``skip`` annotation (fixture/beforeAll died)  critical
  S3  an ``expected_total: 0`` reason fired                                critical
  S4a a known reason skipped more tests than expected on a project         warning
  S4b fewer than expected (tests deleted, or more ran)                     notice
  S4c no expectation on file: differs from the 7-run median                notice
  S5  the browser matrix differs from ``expected_projects``                warning (suppresses S4)
  S6  a test skipped tonight that passed in the previous same-matrix run   warning
"""

from __future__ import annotations

import json
import pathlib
import re
import statistics
from collections import defaultdict

UNKNOWN_PREFIX = "_unknown:"
UNANNOTATED = "_unannotated"


def load_allowlist(path: pathlib.Path | str | None) -> tuple[dict, str]:
    """Return (allowlist, error). A missing/invalid file gives an empty list and an error string."""
    empty = {"expected_projects": [], "reasons": []}
    if path is None:
        return empty, "no allow-list path"
    path = pathlib.Path(path)
    if not path.exists():
        return empty, f"allow-list not found: {path}"
    try:
        data = json.loads(path.read_text())
    except ValueError as exc:
        return empty, f"allow-list unparsable: {exc}"
    reasons = []
    for entry in data.get("reasons", []):
        if not entry.get("id") or not (entry.get("match") or entry.get("pattern")):
            return empty, f"allow-list entry missing id/match/pattern: {entry!r}"
        compiled = re.compile(entry["pattern"]) if entry.get("pattern") else None
        reasons.append({**entry, "_regex": compiled})
    return {"expected_projects": data.get("expected_projects", []), "reasons": reasons}, ""


def match(reason: str, allowlist: dict) -> dict | None:
    for entry in allowlist["reasons"]:
        if entry.get("match") is not None and reason == entry["match"]:
            return entry
    for entry in allowlist["reasons"]:
        regex = entry.get("_regex")
        if regex is not None and regex.fullmatch(reason):
            return entry
    return None


def group(tests: list[dict], allowlist: dict) -> list[dict]:
    """One group per (allow-list id | unknown reason | un-annotated), with per-project counts."""
    groups: dict[str, dict] = {}
    for t in tests:
        if t["status"] != "skipped":
            continue
        reasons = t.get("skip_reasons") or []
        if not reasons:
            gid, entry, text, kind = UNANNOTATED, None, "(no skip annotation)", "unannotated"
        else:
            text = reasons[0]
            entry = match(text, allowlist)
            if entry is None:
                gid, kind = UNKNOWN_PREFIX + text, "unknown"
            else:
                gid, kind = entry["id"], "known"
        g = groups.setdefault(gid, {
            "id": gid, "reason": text, "entry": entry, "kind": kind,
            "by_project": defaultdict(int), "total": 0, "keys": [],
        })
        g["by_project"][t["project"]] += 1
        g["total"] += 1
        g["keys"].append(t["key"])
    for g in groups.values():
        g["by_project"] = dict(sorted(g["by_project"].items()))
    order = {"unannotated": 0, "unknown": 1, "known": 2}
    return sorted(groups.values(), key=lambda g: (order[g["kind"]], -g["total"], g["id"]))


def expected_for(entry: dict | None, project: str) -> int | None:
    if entry is None:
        return None
    if "expected_total" in entry:
        return 0 if entry["expected_total"] == 0 else None
    return (entry.get("expected") or {}).get(project, 0)


def to_record(groups: list[dict]) -> dict:
    return {g["id"]: dict(g["by_project"]) for g in groups}


def _median_prior(prior: list[dict], gid: str, project: str) -> float | None:
    values = []
    for rec in prior[-7:]:
        skips = ((rec.get("playwright") or {}).get("skips") or {})
        values.append(skips.get(gid, {}).get(project, 0))
    return statistics.median(values) if values else None


def analyse(groups: list[dict], allowlist: dict, prior: list[dict], projects_present: list[str],
            tests_by_key: dict, previous: dict | None) -> list[dict]:
    anomalies: list[dict] = []
    section = "Skipped by reason"

    expected_projects = set(allowlist.get("expected_projects") or [])
    matrix_ok = not expected_projects or set(projects_present) == expected_projects
    if expected_projects and not matrix_ok:
        anomalies.append({
            "id": "S5", "severity": "warning", "section": section,
            "title": "Browser matrix differs from the expected one",
            "detail": f"ran: {', '.join(projects_present) or 'none'}; expected: {', '.join(sorted(expected_projects))}. "
                      "Per-reason expectations are not checked for this run.",
        })

    for g in groups:
        if g["kind"] == "unannotated":
            anomalies.append({
                "id": "S2", "severity": "critical", "section": section,
                "title": f"{g['total']} skipped test(s) carry no skip reason",
                "detail": "A skipped test without a `test.skip(...)` annotation usually means a fixture or beforeAll "
                          f"failed before the test body ran. Projects: {_fmt_projects(g['by_project'])}.",
            })
            continue
        if g["kind"] == "unknown":
            anomalies.append({
                "id": "S1", "severity": "critical", "section": section,
                "title": "Skip reason not in the allow-list",
                "detail": f"\"{g['reason']}\" skipped {g['total']} test(s) on {_fmt_projects(g['by_project'])}. "
                          "Add it to .github/nightly/known_skips.json if it is intentional.",
            })
            continue
        entry = g["entry"]
        if entry.get("expected_total") == 0:
            anomalies.append({
                "id": "S3", "severity": "critical", "section": section,
                "title": f"\"{entry['id']}\" fired ({g['total']}) but should never fire on a nightly run",
                "detail": entry.get("explain", "") + f" Projects: {_fmt_projects(g['by_project'])}.",
            })
            continue
        if not matrix_ok:
            continue
        if entry.get("expected"):
            for project in sorted(set(projects_present) | set(g["by_project"])):
                observed = g["by_project"].get(project, 0)
                expected = (entry["expected"] or {}).get(project, 0)
                if observed > expected:
                    anomalies.append({
                        "id": "S4a", "severity": "warning", "section": section,
                        "title": f"\"{entry['id']}\" skipped more than expected on {project}",
                        "detail": f"observed {observed}, expected {expected}. New specs under this reason, or a spec that "
                                  "used to run there. Update the allow-list if intentional.",
                    })
                elif observed < expected:
                    anomalies.append({
                        "id": "S4b", "severity": "notice", "section": section,
                        "title": f"\"{entry['id']}\" skipped fewer than expected on {project}",
                        "detail": f"observed {observed}, expected {expected}. Either tests were removed or more of them ran.",
                    })
        else:
            for project, observed in g["by_project"].items():
                med = _median_prior(prior, entry["id"], project)
                if med is not None and prior and abs(observed - med) >= 1:
                    anomalies.append({
                        "id": "S4c", "severity": "notice", "section": section,
                        "title": f"\"{entry['id']}\" on {project} differs from its recent median",
                        "detail": f"observed {observed}, 7-run median {med:g}.",
                    })

    # S6: newly skipped keys that passed last time (compare-reports' coverage-lost rule).
    if previous and matrix_ok:
        prev_pw = previous.get("playwright") or {}
        prev_skipped = set(prev_pw.get("skipped_keys") or [])
        prev_bad = set(prev_pw.get("failed") or []) | set(prev_pw.get("flaky") or [])
        prev_seen = set(prev_pw.get("durations") or {}) | prev_skipped | prev_bad
        newly = [k for k, t in tests_by_key.items()
                 if t["status"] == "skipped" and k in prev_seen and k not in prev_skipped and k not in prev_bad]
        if newly:
            anomalies.append({
                "id": "S6", "severity": "warning", "section": section,
                "title": f"{len(newly)} test(s) ran last night but were skipped tonight",
                "detail": "; ".join(newly[:5]) + (" …" if len(newly) > 5 else ""),
            })
    return anomalies


def _fmt_projects(by_project: dict) -> str:
    return ", ".join(f"{p} ({n})" for p, n in by_project.items()) or "none"
