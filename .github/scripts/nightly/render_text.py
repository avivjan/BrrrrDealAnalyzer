"""Plain-text alternative. Every line the v1 email printed is still printed, in the same order."""

from __future__ import annotations

from .playwright_report import STATUS_LABELS, test_label


def fmt_secs(ms: float) -> str:
    return f"{ms / 1000:.2f}s"


def render_text(ctx: dict) -> str:
    s = ctx["summary"]
    a = ctx["analysis"]
    lines = [
        "=" * 44,
        f"BrrrrDealAnalyzer nightly test session: {ctx['verdict']} - {ctx['headline']}",
        ctx["when"],
        "=" * 44,
        "",
        "Tests by suite: " + " | ".join(
            f"{name} {part['total']}" + (f" ({part['failed']} failed)" if part["failed"] else "")
            if part.get("available") else f"{name} no report"
            for name, part in (("Playwright", ctx["totals"]["parts"]["playwright"]),
                               ("Backend (pytest)", ctx["totals"]["parts"]["backend"]),
                               ("Frontend (vitest)", ctx["totals"]["parts"]["frontend"]))),
        "",
        "Jobs:",
        *[f"  {label}: {outcome}" for label, outcome in ctx["jobs"]],
        "",
    ]

    findings = a["findings"]
    lines += ["Anomalies:"]
    if findings:
        lines += [f"  [{f['severity'].upper()}] {f['title']} - {f['detail']}" for f in findings]
    else:
        lines += [f"  none against the allow-list or the last {ctx['history']['count']} run(s)."]
    lines += [""]

    lines += ["Playwright Session Report", "-" * 44]
    if s["available"]:
        lines += [
            f"Session finished with exit code {ctx['exit_code']} "
            f"({'All tests passed' if s['failed'] == 0 else 'Failures present'})",
            f"Total test calls (run): {s['total_calls']}",
            "",
            "Test Outcomes:",
            f"  Passed: {s['passed']}",
            f"  Failed: {s['failed']}",
            f"  Skipped: {s['skipped']}",
            "",
            "No tests were rerun." if s["rerun_tests"] == 0 else f"{s['rerun_tests']} test(s) were rerun ({s['flaky']} flaky).",
            "",
            "Results by browser:",
            *[
                f"  {project}: " + ", ".join(
                    f"{counts.get(k, 0)} {STATUS_LABELS[k]}" for k in STATUS_LABELS if counts.get(k)
                )
                for project, counts in s["per_project"].items()
            ],
        ]
        if s["failed_tests"]:
            lines += ["", f"Failed tests ({len(s['failed_tests'])}):"]
            for t in s["failed_tests"][:40]:
                cls = a["failure_classes"].get(t["key"])
                tag = ""
                if cls:
                    tag = "  [first seen]" if cls["first_seen"] else f"  [recurring, {cls['recurring']} of last {cls['window']}]"
                lines.append(f"  FAILED [{t['project']}] {test_label(t)}{tag}")
        lines += ["", f"Top {len(s['top'])} Longest-Running Tests:", "-" * 44]
        for t in s["top"]:
            slow = a["slow"].get(t["key"])
            tag = f"  [slower than usual: {slow['ratio']:.1f}x median]" if slow else ""
            lines.append(f"  [{t['project']}] {test_label(t)}: {fmt_secs(t['duration_ms'])}{tag}")
    else:
        lines.append(f"No Playwright JSON report was produced (job result: {ctx['e2e_outcome']}, exit code {ctx['exit_code']}).")

    # --- suites -------------------------------------------------------------
    lines += ["", "Backend and frontend suites", "-" * 44]
    for name, suite in (("Backend (pytest)", ctx["junit"]["backend"]), ("Frontend (vitest)", ctx["junit"]["frontend"])):
        if not suite["available"]:
            lines.append(f"  {name}: {suite['error'] or 'no report'}")
            continue
        lines.append(f"  {name}: {suite['passed']} passed, {suite['failures'] + suite['errors']} failed, "
                     f"{suite['skipped']} skipped, {suite['tests']} total in {suite['time_s']:.1f}s")
        for c in suite["failed"][:10]:
            lines.append(f"    FAILED {c['classname']}::{c['name']}")
        for c in suite["slowest"][:5]:
            lines.append(f"    slow   {c['classname']}::{c['name']}: {c['time_s']:.2f}s")

    # --- skips ----------------------------------------------------------------
    lines += ["", "Skipped by reason", "-" * 44]
    if not ctx["skips"]["groups"]:
        lines.append("  no skipped tests" if s["available"] else "  no report")
    for g in ctx["skips"]["groups"]:
        if g["kind"] == "known":
            entry = g["entry"]
            exp = _expected_text(entry, g["by_project"])
            flag = "SHOULD NEVER FIRE - " if entry.get("expected_total") == 0 else ""
            lines.append(f"  {g['total']:4d}  {flag}{entry['category']}: \"{g['reason']}\"{exp}")
            lines.append(f"        {entry.get('explain', '')}")
        elif g["kind"] == "unknown":
            lines.append(f"  {g['total']:4d}  UNKNOWN REASON: \"{g['reason']}\"")
        else:
            lines.append(f"  {g['total']:4d}  NO SKIP ANNOTATION (fixture failure?)")
        lines.append("        " + ", ".join(f"{p}: {n}" for p, n in g["by_project"].items()))

    # --- trends -----------------------------------------------------------------
    lines += ["", "Trends", "-" * 44]
    if ctx["history"]["count"] == 0:
        lines.append("  first run: history starts today.")
    else:
        for r in ctx["trend_rows"]:
            lines.append(f"  {r['label']:>7}  #{r['number']}  {r['verdict']:4s}  {r['passed']} passed, "
                         f"{r['failed']} failed, {r['skipped']} skipped, {r['minutes']:.1f} min")
    if a["spec_files"]:
        lines += ["", "Longest-running spec files:"]
        for row in a["spec_files"]:
            lines.append(f"  {row['ms'] / 1000:7.1f}s  {row['file']}  ({row['trend']})")

    # --- coverage ---------------------------------------------------------------
    lines += ["", "Coverage gaps", "-" * 44]
    cov = ctx["coverage"]
    if cov["status"] == "not_wired":
        lines.append("  coverage is not wired yet:")
        lines += [f"    - {step}" for step in cov["steps"]]
    for name, c in (("Backend", cov["backend"]), ("Frontend", cov["frontend"])):
        if c["available"]:
            pct = f"{c['pct']:.1f}%" if c["pct"] is not None else "n/a"
            lines.append(f"  {name}: {pct} line coverage; lowest: " + ", ".join(f"{p} ({v:.0f}%)" for p, v, _ in c["lowest"]))
        elif cov["status"] != "not_wired":
            lines.append(f"  {name}: {c['error'] or 'no coverage report'}")

    lines += [
        "-" * 44,
        "All tests passed! Well done." if ctx["verdict"] == "PASS" else "Some checks failed.",
        "=" * 44,
        "",
        f"Run and HTML report artifact: {ctx['run_url']}",
    ]
    return "\n".join(lines)


def _expected_text(entry: dict, by_project: dict) -> str:
    if "expected_total" in entry:
        return f"  (expected {entry['expected_total']})"
    exp = entry.get("expected") or {}
    if not exp:
        return ""
    return f"  (expected {sum(exp.values())}, observed {sum(by_project.values())})"
