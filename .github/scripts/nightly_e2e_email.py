"""Email the nightly result, pass or fail, as a styled HTML report.

Usage: nightly_e2e_email.py <playwright-json-report>

Reads the Playwright JSON reporter output and sends a session report over
Gmail SMTP (SSL, port 465) with a plain-text alternative. Configuration comes
from the environment:

    CI_OUTCOME        result of the backend + frontend CI job (success / failure /
                      cancelled / skipped); optional
    BACKEND_OUTCOME   result of the "Backend tests" job inside it; optional
    FRONTEND_OUTCOME  result of the "Frontend tests + build" job inside it; optional
    E2E_OUTCOME       result of the Playwright job
    E2E_EXIT_CODE     exit code of `npm run e2e`; optional
    RUN_URL           link to the workflow run (the HTML report is an artifact there)
    MAIL_TO           recipient
    MAIL_USERNAME     Gmail address used as the sender (repository secret)
    MAIL_PASSWORD     Gmail app password for that address (repository secret)

Exits non-zero, with a clear message, when the secrets are missing so the job
turns red instead of silently sending nothing.
"""

from __future__ import annotations

import datetime as _dt
import html
import json
import os
import pathlib
import smtplib
import sys
from collections import defaultdict
from email.message import EmailMessage

TOP_N = 17

STATUS_LABELS = {
    "expected": "passed",
    "unexpected": "failed",
    "flaky": "flaky",
    "skipped": "skipped",
}

# Palette (inline, for email clients).
GREEN = "#16a34a"
RED = "#dc2626"
AMBER = "#d97706"
GREY = "#6b7280"
INK = "#111827"
MUTED = "#4b5563"
LINE = "#e5e7eb"
PANEL = "#f9fafb"
PAGE = "#eef2f7"
MONO = "SFMono-Regular, Menlo, Consolas, 'Liberation Mono', monospace"
SANS = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"


# --------------------------------------------------------------------------
# Report parsing
# --------------------------------------------------------------------------

def walk_tests(suite: dict, chain: list[str], out: list[dict]) -> None:
    """Flatten Playwright's nested suites into one record per test."""
    for spec in suite.get("specs", []):
        parts = [p for p in chain if p] + [spec.get("title", "")]
        for test in spec.get("tests", []):
            results = test.get("results", [])
            out.append({
                "project": test.get("projectName", "?"),
                "status": test.get("status", "?"),
                "file": spec.get("file", ""),
                "title": " > ".join(p for p in parts if p),
                "calls": len(results),
                "reruns": sum(1 for r in results if r.get("retry", 0) > 0),
                "duration_ms": max((r.get("duration", 0) for r in results), default=0),
            })
    for child in suite.get("suites", []):
        # A file-level suite's title is the file path; drop it from the chain.
        title = child.get("title", "")
        next_chain = chain + ([] if title == child.get("file") or title.endswith(".ts") else [title])
        walk_tests(child, next_chain, out)


def load_report(path: pathlib.Path) -> dict | None:
    if not path.exists():
        return None
    return json.loads(path.read_text())


def summarise(report: dict | None) -> dict:
    """Everything the template shows, computed once."""
    if report is None:
        return {
            "available": False,
            "tests": [],
            "passed": 0, "failed": 0, "skipped": 0, "flaky": 0,
            "total_calls": 0, "rerun_tests": 0, "duration_ms": 0,
            "per_project": {}, "failed_tests": [], "top": [],
        }

    tests: list[dict] = []
    for suite in report.get("suites", []):
        walk_tests(suite, [], tests)

    stats = report.get("stats", {})
    per_project: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for t in tests:
        per_project[t["project"]][t["status"]] += 1

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
    }


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------

def fmt_secs(ms: float) -> str:
    return f"{ms / 1000:.2f}s"


def fmt_minutes(ms: float) -> str:
    return f"{ms / 1000 / 60:.1f} min"


def outcome_colour(outcome: str) -> str:
    return {"success": GREEN, "failure": RED, "cancelled": AMBER}.get(outcome, GREY)


def pill(text: str, colour: str) -> str:
    return (
        f'<span style="display:inline-block;padding:2px 10px;border-radius:999px;'
        f'background:{colour};color:#ffffff;font-size:12px;font-weight:600;'
        f'letter-spacing:.02em;text-transform:uppercase;">{html.escape(text)}</span>'
    )


def test_label(t: dict) -> str:
    return f"{t['file']}::{t['title']}"


def render_html(ctx: dict) -> str:
    s = ctx["summary"]
    ok = ctx["verdict"] == "PASS"
    accent = GREEN if ok else RED
    e = html.escape

    # --- summary tiles -----------------------------------------------------
    tiles = [
        ("Passed", s["passed"], GREEN),
        ("Failed", s["failed"], RED if s["failed"] else GREY),
        ("Skipped", s["skipped"], AMBER if s["skipped"] else GREY),
        ("Total test calls", s["total_calls"], INK),
    ]
    tile_cells = "".join(
        f'<td width="25%" style="padding:6px;">'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        f'style="background:{PANEL};border:1px solid {LINE};border-radius:10px;">'
        f'<tr><td style="padding:14px 12px;text-align:center;">'
        f'<div style="font-family:{SANS};font-size:30px;font-weight:700;color:{colour};line-height:1;">{value}</div>'
        f'<div style="font-family:{SANS};font-size:12px;color:{MUTED};margin-top:6px;text-transform:uppercase;letter-spacing:.04em;">{e(label)}</div>'
        f'</td></tr></table></td>'
        for label, value, colour in tiles
    )

    # --- job outcomes -------------------------------------------------------
    job_rows = []
    for label, outcome in ctx["jobs"]:
        job_rows.append(
            f'<tr><td style="padding:8px 0;border-bottom:1px solid {LINE};font-family:{SANS};font-size:14px;color:{INK};">{e(label)}</td>'
            f'<td align="right" style="padding:8px 0;border-bottom:1px solid {LINE};">{pill(outcome, outcome_colour(outcome))}</td></tr>'
        )

    # --- session lines ------------------------------------------------------
    exit_code = ctx["exit_code"]
    if s["available"]:
        session_line = (
            f"Session finished with exit code {e(str(exit_code))} "
            f"({'All tests passed' if s['failed'] == 0 and exit_code in ('0', 0) else 'Failures present'})"
        )
        duration_line = f"Playwright wall-clock: {fmt_minutes(s['duration_ms'])}"
    else:
        session_line = f"No Playwright JSON report was produced (job result: {e(ctx['e2e_outcome'])}, exit code {e(str(exit_code))})"
        duration_line = ""
    rerun_line = (
        "No tests were rerun."
        if s["rerun_tests"] == 0
        else f"{s['rerun_tests']} test(s) were rerun ({s['flaky']} flaky)."
    )
    rerun_colour = GREEN if s["rerun_tests"] == 0 else AMBER

    # --- per-browser table --------------------------------------------------
    browser_rows = []
    for project, counts in s["per_project"].items():
        cells = "".join(
            f'<td align="center" style="padding:8px 6px;border-bottom:1px solid {LINE};font-family:{MONO};font-size:13px;'
            f'color:{colour if counts.get(key) else GREY};font-weight:{"700" if counts.get(key) else "400"};">{counts.get(key, 0)}</td>'
            for key, colour in (("expected", GREEN), ("unexpected", RED), ("flaky", AMBER), ("skipped", GREY))
        )
        browser_rows.append(
            f'<tr><td style="padding:8px 6px;border-bottom:1px solid {LINE};font-family:{SANS};font-size:13px;color:{INK};">{e(project)}</td>{cells}</tr>'
        )
    browser_table = (
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0">'
        f'<tr>'
        f'<th align="left" style="padding:6px;font-family:{SANS};font-size:11px;color:{MUTED};text-transform:uppercase;letter-spacing:.04em;border-bottom:2px solid {LINE};">Browser project</th>'
        + "".join(
            f'<th style="padding:6px;font-family:{SANS};font-size:11px;color:{MUTED};text-transform:uppercase;letter-spacing:.04em;border-bottom:2px solid {LINE};">{h}</th>'
            for h in ("Passed", "Failed", "Flaky", "Skipped")
        )
        + "</tr>" + "".join(browser_rows) + "</table>"
    ) if browser_rows else f'<div style="font-family:{SANS};font-size:13px;color:{MUTED};">No per-browser data.</div>'

    # --- failed tests -------------------------------------------------------
    failed_block = ""
    if s["failed_tests"]:
        items = "".join(
            f'<tr><td style="padding:6px 8px;border-left:3px solid {RED};background:#fef2f2;font-family:{MONO};font-size:12px;color:#7f1d1d;">'
            f'<span style="color:{RED};font-weight:700;">FAILED</span> [{e(t["project"])}] {e(test_label(t))}</td></tr>'
            for t in s["failed_tests"][:40]
        )
        more = (
            f'<tr><td style="padding:6px 8px;font-family:{SANS};font-size:12px;color:{MUTED};">... and {len(s["failed_tests"]) - 40} more</td></tr>'
            if len(s["failed_tests"]) > 40 else ""
        )
        failed_block = section(
            f"Failed tests ({len(s['failed_tests'])})",
            f'<table role="presentation" width="100%" cellpadding="0" cellspacing="2">{items}{more}</table>',
        )

    # --- top N longest --------------------------------------------------------
    top_rows = []
    max_ms = max((t["duration_ms"] for t in s["top"]), default=1) or 1
    for i, t in enumerate(s["top"], 1):
        pct = max(2, int(round(100 * t["duration_ms"] / max_ms)))
        colour = RED if t["status"] == "unexpected" else (AMBER if t["status"] == "flaky" else "#3b82f6")
        top_rows.append(
            f'<tr>'
            f'<td style="padding:7px 6px;border-bottom:1px solid {LINE};font-family:{MONO};font-size:12px;color:{MUTED};text-align:right;">{i}</td>'
            f'<td style="padding:7px 6px;border-bottom:1px solid {LINE};font-family:{MONO};font-size:12px;color:{INK};overflow-wrap:anywhere;">'
            f'<span style="color:{MUTED};">[{e(t["project"])}]</span> {e(test_label(t))}</td>'
            f'<td width="130" style="padding:7px 6px;border-bottom:1px solid {LINE};">'
            f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>'
            f'<td width="{pct}%" style="background:{colour};height:8px;border-radius:4px;font-size:0;line-height:0;">&nbsp;</td>'
            f'<td style="font-size:0;line-height:0;">&nbsp;</td></tr></table></td>'
            f'<td align="right" style="padding:7px 6px;border-bottom:1px solid {LINE};font-family:{MONO};font-size:12px;font-weight:700;color:{INK};white-space:nowrap;">{fmt_secs(t["duration_ms"])}</td>'
            f'</tr>'
        )
    top_table = (
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0">{"".join(top_rows)}</table>'
        if top_rows else f'<div style="font-family:{SANS};font-size:13px;color:{MUTED};">No timing data.</div>'
    )

    # --- closing banner -------------------------------------------------------
    closing = "All tests passed! Well done." if ok else "Some checks failed. See the details above and the run link below."

    body = f"""
<div style="background:{PAGE};padding:24px 12px;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr><td align="center">
<table role="presentation" width="680" cellpadding="0" cellspacing="0" style="max-width:680px;width:100%;background:#ffffff;border-radius:14px;overflow:hidden;border:1px solid {LINE};">

  <tr><td style="background:{accent};padding:26px 28px;">
    <div style="font-family:{SANS};font-size:12px;color:rgba(255,255,255,.85);text-transform:uppercase;letter-spacing:.08em;">BrrrrDealAnalyzer &middot; Nightly test session</div>
    <div style="font-family:{SANS};font-size:28px;font-weight:800;color:#ffffff;margin-top:6px;line-height:1.15;">{e(ctx['verdict'])} &middot; {e(ctx['headline'])}</div>
    <div style="font-family:{SANS};font-size:13px;color:rgba(255,255,255,.9);margin-top:8px;">{e(ctx['when'])}</div>
  </td></tr>

  <tr><td style="padding:18px 22px 6px 22px;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>{tile_cells}</tr></table>
  </td></tr>

  {section("Test session report", f'''
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
      <tr><td style="padding:6px 0;font-family:{MONO};font-size:13px;color:{INK};">{e(session_line)}</td></tr>
      <tr><td style="padding:6px 0;font-family:{MONO};font-size:13px;color:{INK};">Total test calls (run): <b>{s['total_calls']}</b></td></tr>
      <tr><td style="padding:6px 0;font-family:{MONO};font-size:13px;color:{INK};">Test outcomes: <span style="color:{GREEN};font-weight:700;">Passed {s['passed']}</span> &nbsp;&middot;&nbsp; <span style="color:{RED if s['failed'] else GREY};font-weight:700;">Failed {s['failed']}</span> &nbsp;&middot;&nbsp; <span style="color:{AMBER if s['skipped'] else GREY};font-weight:700;">Skipped {s['skipped']}</span></td></tr>
      <tr><td style="padding:6px 0;font-family:{MONO};font-size:13px;color:{rerun_colour};font-weight:700;">{e(rerun_line)}</td></tr>
      {f'<tr><td style="padding:6px 0;font-family:{MONO};font-size:13px;color:{MUTED};">{e(duration_line)}</td></tr>' if duration_line else ''}
    </table>''')}

  {section("Jobs", f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0">{"".join(job_rows)}</table>')}

  {section("Results by browser", browser_table)}

  {failed_block}

  {section(f"Top {len(s['top'])} longest-running tests", top_table)}

  <tr><td style="padding:10px 22px 24px 22px;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{PANEL};border:1px solid {LINE};border-radius:10px;">
      <tr><td style="padding:16px;text-align:center;font-family:{SANS};font-size:16px;font-weight:700;color:{accent};">{e(closing)}</td></tr>
    </table>
    <div style="font-family:{SANS};font-size:12px;color:{MUTED};margin-top:16px;text-align:center;">
      <a href="{e(ctx['run_url'])}" style="color:#2563eb;text-decoration:none;font-weight:600;">Open the workflow run</a>
      &nbsp;&middot;&nbsp; the Playwright HTML report and traces are attached to it as an artifact.
    </div>
  </td></tr>

</table>
</td></tr></table>
</div>"""
    return f"<!doctype html><html><body style=\"margin:0;padding:0;background:{PAGE};\">{body}</body></html>"


def section(title: str, inner: str) -> str:
    return (
        f'<tr><td style="padding:14px 28px 6px 28px;">'
        f'<div style="font-family:{SANS};font-size:12px;font-weight:700;color:{MUTED};text-transform:uppercase;letter-spacing:.08em;padding-bottom:8px;border-bottom:2px solid {LINE};">{html.escape(title)}</div>'
        f'<div style="padding-top:10px;">{inner}</div>'
        f'</td></tr>'
    )


def render_text(ctx: dict) -> str:
    s = ctx["summary"]
    lines = [
        "=" * 44,
        f"BrrrrDealAnalyzer nightly test session: {ctx['verdict']} - {ctx['headline']}",
        ctx["when"],
        "=" * 44,
        "",
        "Jobs:",
        *[f"  {label}: {outcome}" for label, outcome in ctx["jobs"]],
        "",
        "Test Session Report",
        "-" * 44,
    ]
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
            lines += [f"  FAILED [{t['project']}] {test_label(t)}" for t in s["failed_tests"][:40]]
        lines += ["", f"Top {len(s['top'])} Longest-Running Tests:", "-" * 44]
        lines += [f"  [{t['project']}] {test_label(t)}: {fmt_secs(t['duration_ms'])}" for t in s["top"]]
    else:
        lines.append(f"No Playwright JSON report was produced (job result: {ctx['e2e_outcome']}, exit code {ctx['exit_code']}).")
    lines += [
        "-" * 44,
        "All tests passed! Well done." if ctx["verdict"] == "PASS" else "Some checks failed.",
        "=" * 44,
        "",
        f"Run and HTML report artifact: {ctx['run_url']}",
    ]
    return "\n".join(lines)


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def now_in_israel() -> str:
    try:
        from zoneinfo import ZoneInfo
        now = _dt.datetime.now(ZoneInfo("Asia/Jerusalem"))
        return now.strftime("%A, %d %B %Y, %H:%M %Z")
    except Exception:  # pragma: no cover - no tz database
        return _dt.datetime.now(_dt.timezone.utc).strftime("%A, %d %B %Y, %H:%M UTC")


def build_context(report_path: pathlib.Path) -> dict:
    env = os.environ.get
    e2e_outcome = env("E2E_OUTCOME", "unknown")
    ci_outcome = env("CI_OUTCOME", "")
    jobs: list[tuple[str, str]] = []
    if env("BACKEND_OUTCOME"):
        jobs.append(("Backend tests (pytest + Postgres migration smoke)", env("BACKEND_OUTCOME", "")))
    if env("FRONTEND_OUTCOME"):
        jobs.append(("Frontend tests + build (vitest, vue-tsc, vite)", env("FRONTEND_OUTCOME", "")))
    if not jobs and ci_outcome:
        jobs.append(("Backend + frontend CI suites", ci_outcome))
    jobs.append(("Playwright, all browser projects", e2e_outcome))

    verdict = "PASS" if all(o == "success" for _, o in jobs) else "FAIL"
    summary = summarise(load_report(report_path))
    if summary["available"]:
        headline = f"{summary['passed']} passed, {summary['failed']} failed, {summary['skipped']} skipped"
    else:
        headline = "no Playwright report"

    return {
        "verdict": verdict,
        "headline": headline,
        "when": now_in_israel(),
        "jobs": jobs,
        "e2e_outcome": e2e_outcome,
        "exit_code": env("E2E_EXIT_CODE", "") or ("0" if e2e_outcome == "success" else "?"),
        "run_url": env("RUN_URL", ""),
        "summary": summary,
    }


def main(argv: list[str]) -> int:
    if len(argv) not in (2, 3):
        print(__doc__, file=sys.stderr)
        return 2

    ctx = build_context(pathlib.Path(argv[1]))
    html_body = render_html(ctx)
    text_body = render_text(ctx)

    # `--write-html <file>` renders without sending (used to preview the design).
    if len(argv) == 3:
        pathlib.Path(argv[2]).write_text(html_body)
        print(text_body)
        return 0

    username = os.environ.get("MAIL_USERNAME", "")
    password = os.environ.get("MAIL_PASSWORD", "")
    if not username or not password:
        print(
            "::error::NIGHTLY_MAIL_USERNAME / NIGHTLY_MAIL_PASSWORD repository secrets are "
            "not set, so the nightly email cannot be sent. Add them under "
            "Settings > Secrets and variables > Actions.",
            file=sys.stderr,
        )
        return 1

    today = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%d")
    message = EmailMessage()
    message["Subject"] = f"[BrrrrDealAnalyzer] Nightly {ctx['verdict']} · {ctx['headline']} · {today}"
    message["From"] = username
    message["To"] = os.environ.get("MAIL_TO", username)
    message.set_content(text_body)
    message.add_alternative(html_body, subtype="html")

    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=60) as smtp:
        smtp.login(username, password)
        smtp.send_message(message)

    print(f"Sent nightly email: {message['Subject']} -> {message['To']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
