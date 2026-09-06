"""Email the nightly Playwright result, pass or fail.

Usage: nightly_e2e_email.py <playwright-json-report>

Reads the JSON reporter output, builds a per-browser summary and sends it over
Gmail SMTP (SSL, port 465). Configuration comes from the environment:

    E2E_OUTCOME     outcome of the Playwright step: success / failure / cancelled
    RUN_URL         link to the workflow run (the HTML report is an artifact there)
    MAIL_TO         recipient
    MAIL_USERNAME   Gmail address used as the sender (repository secret)
    MAIL_PASSWORD   Gmail app password for that address (repository secret)

Exits non-zero, with a clear message, when the secrets are missing so the job
turns red instead of silently sending nothing.
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import pathlib
import smtplib
import sys
from collections import defaultdict
from email.message import EmailMessage

STATUS_LABELS = {
    "expected": "passed",
    "unexpected": "failed",
    "flaky": "flaky",
    "skipped": "skipped",
}


def walk_tests(suite: dict, out: list[dict]) -> None:
    for spec in suite.get("specs", []):
        for test in spec.get("tests", []):
            out.append({
                "project": test.get("projectName", "?"),
                "status": test.get("status", "?"),
                "title": " > ".join(filter(None, [spec.get("file", ""), spec.get("title", "")])),
            })
    for child in suite.get("suites", []):
        walk_tests(child, out)


def summarise(report_path: pathlib.Path) -> tuple[str, list[str]]:
    """Return (one-line totals, detail lines) from a Playwright JSON report."""
    if not report_path.exists():
        return "No JSON report was produced (the run died before Playwright wrote one).", []

    report = json.loads(report_path.read_text())
    tests: list[dict] = []
    for suite in report.get("suites", []):
        walk_tests(suite, tests)

    stats = report.get("stats", {})
    totals = (
        f"{stats.get('expected', 0)} passed, {stats.get('unexpected', 0)} failed, "
        f"{stats.get('flaky', 0)} flaky, {stats.get('skipped', 0)} skipped "
        f"in {stats.get('duration', 0) / 1000 / 60:.1f} min"
    )

    per_project: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for test in tests:
        per_project[test["project"]][test["status"]] += 1

    lines = ["Per browser project:"]
    for project in sorted(per_project):
        counts = per_project[project]
        parts = [f"{counts[s]} {STATUS_LABELS[s]}" for s in STATUS_LABELS if counts.get(s)]
        lines.append(f"  - {project}: {', '.join(parts) or 'no tests'}")

    failed = [t for t in tests if t["status"] == "unexpected"]
    if failed:
        lines.append("")
        lines.append(f"Failed tests ({len(failed)}):")
        for test in failed[:40]:
            lines.append(f"  - [{test['project']}] {test['title']}")
        if len(failed) > 40:
            lines.append(f"  ... and {len(failed) - 40} more")

    return totals, lines


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2

    username = os.environ.get("MAIL_USERNAME", "")
    password = os.environ.get("MAIL_PASSWORD", "")
    if not username or not password:
        print(
            "::error::NIGHTLY_MAIL_USERNAME / NIGHTLY_MAIL_PASSWORD repository secrets are "
            "not set, so the nightly e2e email cannot be sent. Add them under "
            "Settings > Secrets and variables > Actions.",
            file=sys.stderr,
        )
        return 1

    outcome = os.environ.get("E2E_OUTCOME", "unknown")
    verdict = "PASS" if outcome == "success" else "FAIL"
    today = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%d")
    run_url = os.environ.get("RUN_URL", "")

    totals, detail = summarise(pathlib.Path(argv[1]))

    body_lines = [
        f"Nightly Playwright run: {verdict} ({outcome})",
        f"Date: {today} (UTC)",
        f"Totals: {totals}",
        "",
        *detail,
        "",
        f"Run and HTML report artifact: {run_url}",
    ]

    message = EmailMessage()
    message["Subject"] = f"[BrrrrDealAnalyzer] Nightly e2e {verdict} - {today}"
    message["From"] = username
    message["To"] = os.environ.get("MAIL_TO", username)
    message.set_content("\n".join(body_lines))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=60) as smtp:
        smtp.login(username, password)
        smtp.send_message(message)

    print(f"Sent nightly e2e email: {message['Subject']} -> {message['To']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
