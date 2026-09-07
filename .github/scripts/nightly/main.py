"""CLI: parse the run's artifacts, judge them against the allow-list and history, render and send.

Backward-compatible forms (the v1 script's interface):

    nightly_e2e_email.py <playwright.json>              send
    nightly_e2e_email.py <playwright.json> <out.html>   render only (preview)

Full form:

    nightly_e2e_email.py [--playwright P] [--backend-junit P] [--frontend-junit P]
                         [--backend-coverage P] [--frontend-coverage P]
                         [--history P] [--append-history] [--write-record P] [--window N]
                         [--known-skips P] [--charts auto|png|table|off]
                         [--write-html P] [--write-text P] [--no-send] [--now ISO-8601]

Environment (unchanged from v1): CI_OUTCOME, BACKEND_OUTCOME, FRONTEND_OUTCOME,
E2E_OUTCOME, E2E_EXIT_CODE, RUN_URL, MAIL_TO, MAIL_USERNAME, MAIL_PASSWORD; plus
optional RUN_ID, RUN_NUMBER, RUN_ATTEMPT, GIT_SHA for the history record.
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import pathlib
import smtplib
import sys
from email.message import EmailMessage

from . import anomalies, charts, coverage, history, junit, skips
from .playwright_report import load_report, summarise
from .render_html import HTML_BUDGET, render_html
from .render_text import render_text

HERE = pathlib.Path(__file__).resolve()
REPO_ROOT = HERE.parents[3]
DEFAULT_KNOWN_SKIPS = REPO_ROOT / ".github" / "nightly" / "known_skips.json"


def parse_args(argv: list[str]) -> argparse.Namespace:
    # Legacy positional forms.
    positional = [a for a in argv[1:] if not a.startswith("--")]
    if len(argv) in (2, 3) and len(positional) == len(argv) - 1:
        argv = [argv[0], "--playwright", positional[0]] + (["--write-html", positional[1], "--no-send"] if len(positional) == 2 else [])
    p = argparse.ArgumentParser(prog="nightly_e2e_email.py", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--playwright")
    p.add_argument("--backend-junit")
    p.add_argument("--frontend-junit")
    p.add_argument("--backend-coverage")
    p.add_argument("--frontend-coverage")
    p.add_argument("--history")
    p.add_argument("--append-history", action="store_true")
    p.add_argument("--write-record")
    p.add_argument("--window", type=int, default=30)
    p.add_argument("--known-skips", default=str(DEFAULT_KNOWN_SKIPS))
    p.add_argument("--charts", choices=("auto", "png", "table", "off"), default="auto")
    p.add_argument("--write-html")
    p.add_argument("--write-text")
    p.add_argument("--no-send", action="store_true")
    p.add_argument("--now", help="ISO-8601 timestamp to use instead of the wall clock (deterministic previews)")
    return p.parse_args(argv[1:])


def now_utc(override: str | None) -> dt.datetime:
    if override:
        return dt.datetime.fromisoformat(override.replace("Z", "+00:00")).astimezone(dt.timezone.utc)
    return dt.datetime.now(dt.timezone.utc)


def when_in_israel(now: dt.datetime) -> str:
    try:
        from zoneinfo import ZoneInfo
        return now.astimezone(ZoneInfo("Asia/Jerusalem")).strftime("%A, %d %B %Y, %H:%M %Z")
    except Exception:  # pragma: no cover - no tz database
        return now.strftime("%A, %d %B %Y, %H:%M UTC")


def build_context(args: argparse.Namespace) -> dict:
    env = os.environ.get
    now = now_utc(args.now)

    # --- jobs & verdict (v1 semantics) ----------------------------------------
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

    # --- sources ---------------------------------------------------------------
    summary = summarise(load_report(args.playwright))
    backend = junit.parse(args.backend_junit)
    frontend = junit.parse(args.frontend_junit)
    cov_backend = coverage.parse_pytest_cov_json(args.backend_coverage)
    cov_frontend = coverage.parse_vitest_summary(args.frontend_coverage)
    allowlist, allowlist_error = skips.load_allowlist(args.known_skips)
    prior, malformed = history.load_tail(args.history, args.window)

    # --- record for tonight ------------------------------------------------------
    groups = skips.group(summary["tests"], allowlist)
    run = {
        "id": _int(env("RUN_ID")), "number": _int(env("RUN_NUMBER")), "attempt": _int(env("RUN_ATTEMPT")),
        "sha": (env("GIT_SHA") or "")[:7], "url": env("RUN_URL", ""),
        "started": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    exit_code = env("E2E_EXIT_CODE", "") or ("0" if e2e_outcome == "success" else "?")
    record = history.build_record(
        run=run, verdict=verdict,
        jobs={"ci": ci_outcome, "backend": env("BACKEND_OUTCOME", ""), "frontend": env("FRONTEND_OUTCOME", ""),
              "playwright": e2e_outcome, "exit_code": exit_code},
        summary=summary, skips_record=skips.to_record(groups), backend=backend, frontend=frontend,
        coverage_backend=cov_backend, coverage_frontend=cov_frontend, prior=prior,
    )
    # Headline numbers add every suite (Playwright + pytest + vitest); the Playwright-only
    # figures keep their own section further down.
    totals = anomalies.suite_totals(record)
    headline = (f"{totals['passed']} passed, {totals['failed']} failed, {totals['skipped']} skipped"
                if totals["total"] else "no test reports")
    comparable = history.comparable(prior, record)
    prev = history.previous(prior, record)
    week = history.week_ago(prior, record, now)

    # --- analysis ------------------------------------------------------------------
    skip_findings = skips.analyse(groups, allowlist, comparable, summary["projects_present"],
                                  summary["tests_by_key"], prev) if summary["available"] else []
    analysis = anomalies.collect(record, comparable, prev, skip_findings, backend, frontend,
                                 cov_backend, cov_frontend, "", malformed, allowlist_error)
    analysis["deltas"] = anomalies.tile_deltas(record, prev, week)

    chart_records = comparable + [record]
    slow_keys = [t["key"] for t in summary["top"][:5]]
    return {
        "verdict": verdict, "headline": headline, "when": when_in_israel(now), "now": now,
        "jobs": jobs, "e2e_outcome": e2e_outcome, "exit_code": exit_code, "run_url": env("RUN_URL", ""),
        "summary": summary, "totals": totals,
        "junit": {"backend": backend, "frontend": frontend},
        "coverage": {"backend": cov_backend, "frontend": cov_frontend,
                     "status": coverage.status(cov_backend, cov_frontend), "steps": coverage.NOT_WIRED_STEPS},
        "skips": {"groups": groups, "allowlist": allowlist},
        "history": {"count": len(comparable), "prior_total": len(prior), "chart_note": ""},
        "analysis": analysis,
        "record": record,
        "chart_records": chart_records,
        "slow_keys": slow_keys,
        "trend_rows": charts.fallback_rows(chart_records),
    }


def _int(value: str | None) -> int | None:
    try:
        return int(value) if value not in (None, "") else None
    except ValueError:
        return None


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    if not args.playwright and not (args.backend_junit or args.frontend_junit):
        print(__doc__, file=sys.stderr)
        return 2

    ctx = build_context(args)

    # Persist tonight's record before anything that can fail (SMTP, secrets).
    if args.write_record:
        history.write_record(args.write_record, ctx["record"])
    if args.append_history and args.history:
        history.append(args.history, ctx["record"])

    # Charts.
    images: dict[str, bytes] = {}
    if args.charts in ("auto", "png"):
        try:
            images = charts.render_all(ctx["chart_records"], ctx["skips"]["allowlist"], ctx["slow_keys"])
        except Exception as exc:  # never let a chart kill the mail
            print(f"::warning::chart rendering failed, falling back to a table: {exc!r}", file=sys.stderr)
            images = {}
    if not images and ctx["history"]["count"] > 0:
        ctx["history"]["chart_note"] = ("Charts need matplotlib on the runner and at least two comparable runs; "
                                        "showing the last runs as a table.")
    cids = {name: f"nightly-{name}@brrrrdealanalyzer" for name in images}

    html_body = render_html(ctx, cids)
    text_body = render_text(ctx)
    if len(html_body) > HTML_BUDGET:
        print(f"::warning::HTML body is {len(html_body)} bytes; Gmail clips around 102 KB", file=sys.stderr)

    if args.write_html:
        # Preview files: the mail embeds charts by Content-ID, a browser needs file names.
        out_path = pathlib.Path(args.write_html)
        preview_html = html_body
        for name, png in images.items():
            png_name = f"{out_path.stem}-{name}.png"
            (out_path.parent / png_name).write_bytes(png)
            preview_html = preview_html.replace(f"cid:{cids[name]}", png_name)
        out_path.write_text(preview_html)
    if args.write_text:
        pathlib.Path(args.write_text).write_text(text_body)
    if args.no_send:
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

    today = ctx["now"].strftime("%Y-%m-%d")
    message = EmailMessage()
    message["Subject"] = f"[BrrrrDealAnalyzer] Nightly {ctx['verdict']} · {ctx['headline']} · {today}"
    message["From"] = username
    message["To"] = os.environ.get("MAIL_TO", username)
    message.set_content(text_body)
    message.add_alternative(html_body, subtype="html")
    if images:
        html_part = message.get_payload()[1]
        for name, png in images.items():
            html_part.add_related(png, maintype="image", subtype="png", cid=f"<{cids[name]}>",
                                  filename=f"{name}.png")

    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=60) as smtp:
        smtp.login(username, password)
        smtp.send_message(message)

    print(f"Sent nightly email: {message['Subject']} -> {message['To']}")
    return 0
