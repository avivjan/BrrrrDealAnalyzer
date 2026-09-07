"""Build realistic inputs for previewing the nightly email without a CI run.

Writes ``out/pass/`` and ``out/fail/`` (gitignored) next to this file, each with a
full five-project Playwright JSON report whose skips follow the allow-list exactly,
JUnit XML for both suites, both coverage summaries and a ``history.jsonl`` of 22
earlier nightly runs. The FAIL variant injects: two failures (one recurring, one
first seen), one flaky test, one unknown skip reason, one un-annotated skip, one
zoomed-out-device skip, a test that is 2× slower than its median, and one failing
backend test.

    python3 .github/scripts/nightly/make_preview_fixtures.py
"""

from __future__ import annotations

import datetime as dt
import json
import pathlib
import random
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from nightly import history, junit, skips  # noqa: E402
from nightly.playwright_report import summarise  # noqa: E402

OUT = HERE / "out"
ROOT_DIR = "/home/runner/work/BrrrrDealAnalyzer/BrrrrDealAnalyzer/frontend/e2e"
FUNCTIONAL = ["chromium", "webkit", "Mobile Safari", "Mobile Chrome"]
PROJECTS = FUNCTIONAL + ["chromium-motion"]

R = {  # exact reason strings from frontend/e2e
    "axe": "the axe baseline is recorded and replayed on chromium only",
    "token": "token resolution is engine-independent; checked on chromium only",
    "shell": "shell layout is engine-independent; checked on chromium only",
    "drag": "drag characterization is recorded and replayed on chromium only",
    "pure": "a pure comparison needs checking once, not once per engine",
    "prop": "custom-property resolution is engine-independent; checked on chromium only",
    "perf": "performance entries are Chromium's; this test runs on chromium only",
    "perf_motion": "performance entries are Chromium's; this test runs on chromium-motion only",
    "motion": "the motion-on guard; the other projects run with reducedMotion: reduce",
    "wheel": "wheel emulation is Chromium-only",
    "zoom": "the header overflows this device, so the page is zoomed out and its controls cannot be driven",
}

# (file, describe, [titles], rule) — rule decides which projects skip and why.
#   None: runs everywhere; "chromium_only:<reason>": skips on webkit/Mobile Safari/Mobile Chrome;
#   "motion_only:<reason>": @motion test, skips on the four functional projects; "wheel": skips on WebKit projects.
SPECS: list[tuple[str, str, list[str], str | None]] = [
    ("checks/alignment.spec.ts", "alignment", [f"control rows line up on {r}" for r in ("analyze", "my-deals", "bought-deals", "liquidity")], None),
    ("checks/axe-modals.spec.ts", "overlays and seeded boards (desktop)", [f"axe passes: {m}" for m in ("deal modal", "bought modal", "command palette", "appearance drawer", "settings panel")], "chromium_only:axe"),
    ("checks/axe-modals.spec.ts", "every route at 390px", [f"axe passes at 390px: {r}" for r in ("/", "/analyze", "/my-deals", "/bought-deals", "/liquidity", "/reps")], "chromium_only:axe"),
    ("checks/chart-tokens.spec.ts", "chart tokens", ["every --chart-* token resolves to a colour on /liquidity"], "chromium_only:prop"),
    ("checks/modal-scroll.spec.ts", "deal modal", ["the page behind the modal does not scroll", "a wheel over the content scrolls the modal", "the header stays pinned", "close restores the page scroll"], "wheel:1"),
    ("checks/modal-scroll.spec.ts", "bought modal", ["the page behind the modal does not scroll", "a wheel over the content scrolls the modal", "the header stays pinned", "close restores the page scroll"], "wheel:1"),
    ("checks/no-live-tweens.spec.ts", "", ["no GSAP tween outlives its interaction, on any route @motion"], "motion_only:motion"),
    ("checks/perf.spec.ts", "cls", [f"{r}: no layout shift after load" for r in ("/", "/analyze", "/my-deals", "/bought-deals", "/liquidity", "/reps")], "chromium_only:perf"),
    ("checks/perf.spec.ts", "idle boards", ["my-deals: no long task while the board sits idle with 20 cards", "bought-deals: no long task while the board sits idle with 8 cards"], "chromium_only:perf"),
    ("checks/perf.spec.ts", "idle boards", ["my-deals: no long task while the board sits idle with 20 cards @motion", "bought-deals: no long task while the board sits idle with 8 cards @motion"], "motion_only:perf_motion"),
    ("checks/perf.spec.ts", "chart", ["liquidity chart pan stays under budget"], "chromium_only:perf"),
    ("checks/perf.spec.ts", "bundle", ["bundle: gzip size of dist/assets/*.js, for the progress file"], "chromium_only:perf"),
    ("checks/shell.spec.ts", "desktop", ["sidebar carries every route", "command palette opens with the shortcut"], "chromium_only:shell"),
    ("checks/shell.spec.ts", "390px", ["bottom nav carries every route", "drawer opens and closes"], "chromium_only:shell"),
    ("checks/theme.spec.ts", "", ["every look applies from Settings, changes the display face, and persists", "the mode toggle applies instantly and persists across a reload in this browser", "a second browser context starts from the defaults, whatever the first chose", "every --chart-* token resolves to a colour in all eight look × mode sets", "the Appearance drawer lists four looks", "the wordmark uses the display face", "reduced motion is respected"], "chromium_only:token"),
    ("checks/theme.spec.ts", "axe in every look and mode", [f"dashboard and liquidity pass in {look} {mode}" for look in ("aurora", "luxury", "obsidian", "brutal") for mode in ("light", "dark")], "chromium_only:token"),
    ("fixtures/axe.compare.spec.ts", "findRegressions", ["ignores nodes that moved", "flags a new violation", "flags a worse impact", "passes an identical baseline"], "chromium_only:pure"),
    ("flows/a11y.spec.ts", "axe baseline", [f"{r} has no new violations" for r in ("/", "/analyze", "/my-deals", "/bought-deals", "/liquidity", "/reps")], "chromium_only:axe"),
    ("flows/analyze-brrr.spec.ts", "", ["saves a BRRRR deal and lands on My Deals"], None),
    ("flows/analyze-flip.spec.ts", "", ["saves a Flip deal and lands on My Deals"], None),
    ("flows/analyze-validation.spec.ts", "", ["an empty form is refused with field errors"], None),
    ("flows/bought-deals-autosave.spec.ts", "", ["a checklist tick persists", "a stage note persists", "a field edit persists after reload", "a rapid double edit keeps the last value"], None),
    ("flows/bought-deals-drag.spec.ts", "", ["drag advances a stage", "drag back is refused", "drag keeps every tick", "drag across two stages is refused"], "chromium_only:drag"),
    ("flows/deep-link-open.spec.ts", "", ["a deep link opens the deal, clears the query and covers the viewport @motion"], "motion_all"),
    ("flows/landing.spec.ts", "", ["the landing page links to Analyze"], None),
    ("flows/liquidity.spec.ts", "", ["adds a one-off transaction", "settings, a one-off flow and a recurring series all persist", "deletes a recurring series", "the chart reacts to the reserve", "Mercury status shows unconfigured"], None),
    ("flows/modal-double-close.spec.ts", "", ["closing twice does not throw"], None),
    ("flows/move-to-bought.spec.ts", "", ["Move to Bought creates a bought deal in the first stage"], None),
    ("flows/my-deals-autosave.spec.ts", "", ["a field edit persists", "a section change persists", "a stage change persists", "a rapid double edit keeps the last value"], None),
    ("flows/my-deals-duplicate-delete.spec.ts", "", ["duplicate makes an identical copy", "delete removes the card"], None),
    ("flows/pdf-report.spec.ts", "", ["exports a BRRRR PDF report", "exports a Flip PDF report"], None),
    ("flows/pipeline-template.spec.ts", "", ["adds a stage", "renames a stage", "reorders stages"], None),
    ("flows/reps.spec.ts", "", ["logs an activity with the timer", "edits a logged activity", "config status when unconfigured", "filters by month"], None),
    ("flows/send-offer.spec.ts", "", ["an empty offer is refused locally", "a complete offer posts and surfaces the server refusal", "a successful offer closes and resets the modal"], None),
]

BASE_MS = {"pdf-report": 26000, "liquidity": 9000, "theme": 4500, "a11y": 5200, "axe-modals": 3800, "perf": 7000}


def base_duration(file: str, title: str, rng: random.Random) -> float:
    for k, ms in BASE_MS.items():
        if k in file:
            return ms * rng.uniform(0.85, 1.15)
    return rng.uniform(900, 3200)


def build_report(rng: random.Random, started: dt.datetime, *, failures: set[tuple[str, str, str]] = frozenset(),
                 flaky: set[tuple[str, str, str]] = frozenset(), unknown_skip: tuple[str, str, str] | None = None,
                 unannotated_skip: tuple[str, str, str] | None = None, zoom_skip: bool = False,
                 slow: dict[tuple[str, str, str], float] | None = None) -> dict:
    slow = slow or {}
    suites: dict[str, dict] = {}
    stats = {"expected": 0, "unexpected": 0, "flaky": 0, "skipped": 0}
    for file, describe, titles, rule in SPECS:
        file_suite = suites.setdefault(file, {"title": file, "file": file, "specs": [], "suites": []})
        container = file_suite
        if describe:
            container = next((s for s in file_suite["suites"] if s["title"] == describe), None)
            if container is None:
                container = {"title": describe, "file": file, "specs": [], "suites": []}
                file_suite["suites"].append(container)
        for title in titles:
            is_motion = "@motion" in title
            spec = {"title": title, "file": file, "tests": []}
            for project in PROJECTS:
                if project == "chromium-motion" and not is_motion:
                    continue  # grep-filtered, never in the report
                skip_reason = None
                if rule and rule.startswith("chromium_only:") and project in ("webkit", "Mobile Safari", "Mobile Chrome"):
                    skip_reason = R[rule.split(":")[1]]
                elif rule and rule.startswith("motion_only:") and project != "chromium-motion":
                    skip_reason = R[rule.split(":")[1]]
                elif rule == "wheel:1" and "wheel" in title and project in ("webkit", "Mobile Safari"):
                    skip_reason = R["wheel"]
                if zoom_skip and project == "Mobile Chrome" and file == "flows/liquidity.spec.ts" and title.startswith("settings,"):
                    skip_reason = R["zoom"]
                ident = (project, file, title)
                annotations = []
                results = []
                if unknown_skip == ident:
                    skip_reason = "sidebar is lg-only at baseline (checklist)"
                if skip_reason or unannotated_skip == ident:
                    status = "skipped"
                    if skip_reason:
                        annotations = [{"type": "skip", "description": skip_reason,
                                        "location": {"file": f"frontend/e2e/{file}", "line": 23, "column": 8}}]
                    results = [{"status": "skipped", "duration": 0 if not skip_reason else rng.randint(40, 200),
                                "retry": 0, "annotations": annotations, "startTime": started.isoformat()}]
                else:
                    ms = base_duration(file, title, rng) * slow.get(ident, 1.0)
                    if ident in failures:
                        status = "unexpected"
                        results = [{"status": "failed", "duration": ms, "retry": 0, "annotations": [],
                                    "error": {"message": "expect(locator).toBeVisible() failed"}, "startTime": started.isoformat()}]
                    elif ident in flaky:
                        status = "flaky"
                        results = [{"status": "failed", "duration": ms, "retry": 0, "annotations": []},
                                   {"status": "passed", "duration": ms * 0.9, "retry": 1, "annotations": []}]
                    else:
                        status = "expected"
                        results = [{"status": "passed", "duration": ms, "retry": 0, "annotations": [], "startTime": started.isoformat()}]
                stats[status] += 1
                spec["tests"].append({"timeout": 90000, "annotations": annotations, "expectedStatus": "passed",
                                      "projectName": project, "projectId": project, "results": results, "status": status})
            container["specs"].append(spec)
    total_ms = sum(r["duration"] for s in suites.values() for c in [s] + s["suites"] for sp in c["specs"] for t in sp["tests"] for r in t["results"])
    return {
        "config": {"rootDir": ROOT_DIR, "version": "1.62.1", "workers": 1,
                   "projects": [{"name": p, "id": p, "retries": 0, "timeout": 90000} for p in PROJECTS]},
        "suites": list(suites.values()),
        "errors": [],
        "stats": {"startTime": started.isoformat().replace("+00:00", "Z"), "duration": total_ms, **stats},
    }


def junit_backend(failing: bool, rng: random.Random) -> str:
    files = {"tests.test_analyze": 29, "tests.test_deal_crud": 58, "tests.test_db_isolation": 14, "tests.test_refi_timing": 17,
             "tests.test_mcp": 65, "tests.test_mcp_tools": 20, "tests.test_mcp_e2e": 3}
    cases = []
    for cls, n in files.items():
        for i in range(n):
            t = rng.uniform(0.5, 4.0) if "e2e" in cls else rng.uniform(0.005, 0.4) if "analyze" not in cls else rng.uniform(0.01, 1.2)
            name = f"test_{cls.split('_', 1)[1]}_{i:02d}"
            body = ""
            if failing and cls == "tests.test_deal_crud" and i == 7:
                body = '<failure message="assert 200 == 500">AssertionError: assert 200 == 500</failure>'
            cases.append(f'<testcase classname="{cls}" name="{name}" time="{t:.3f}">{body}</testcase>')
    total = sum(files.values())
    return (f'<?xml version="1.0" encoding="utf-8"?><testsuites><testsuite name="pytest" errors="0" failures="{1 if failing else 0}" '
            f'skipped="0" tests="{total}" time="{rng.uniform(4, 7):.3f}">{"".join(cases)}</testsuite></testsuites>')


def junit_frontend(rng: random.Random) -> str:
    files = {"src/components/ui/UiKpiCard.test.ts": 12, "src/views/AnalyzeDeal.contract.test.ts": 9, "src/utils/money.test.ts": 18,
             "scripts/audit/verify-ui.test.mjs": 22, "src/motion/tokens.test.ts": 7, "src/stores/deals.test.ts": 15}
    suites = []
    for f, n in files.items():
        cases = "".join(f'<testcase classname="{f}" name="case {i:02d}" time="{rng.uniform(0.001, 0.08):.4f}"></testcase>' for i in range(n))
        suites.append(f'<testsuite name="{f}" tests="{n}" failures="0" errors="0" skipped="0" time="{rng.uniform(0.2, 1.8):.3f}">{cases}</testsuite>')
    return f'<?xml version="1.0" encoding="UTF-8"?><testsuites name="vitest tests" tests="{sum(files.values())}" failures="0" errors="0" time="{rng.uniform(30, 40):.3f}">{"".join(suites)}</testsuites>'


def coverage_backend(rng: random.Random) -> dict:
    files = {"BL/analyze/common/deal_math.py": (96.2, 210), "BL/reps/common/reps_service.py": (18.4, 160), "BL/email/common/offer_email.py": (22.0, 48),
             "BL/liquidity/common/mercury_client.py": (31.5, 72), "DAL/crud/reps.py": (44.0, 130), "routers/reports.py": (58.3, 64),
             "migrations/runner.py": (37.0, 88), "bootstrap.py": (100.0, 12), "db.py": (100.0, 9)}
    return {"meta": {"version": "7.6.0"}, "files": {k: {"summary": {"percent_covered": v[0], "num_statements": v[1]}} for k, v in files.items()},
            "totals": {"percent_covered": 71.4 + rng.uniform(-0.3, 0.3), "num_statements": sum(v[1] for v in files.values())}}


def coverage_frontend(rng: random.Random) -> dict:
    files = {"src/components/LiquidityChart.vue": (34.1, 260), "src/views/RepsTracker.vue": (41.7, 190), "src/api/index.ts": (88.9, 45),
             "src/stores/liquidity.ts": (52.3, 120), "src/motion/gsap.ts": (61.0, 80), "src/utils/money.ts": (100.0, 40)}
    out = {"total": {"lines": {"total": sum(v[1] for v in files.values()), "covered": 0, "skipped": 0, "pct": 68.9 + rng.uniform(-0.3, 0.3)}}}
    for k, (pct, n) in files.items():
        out[f"/home/runner/work/BrrrrDealAnalyzer/BrrrrDealAnalyzer/frontend/{k}"] = {"lines": {"total": n, "covered": round(n * pct / 100), "skipped": 0, "pct": pct}}
    return out


def record_for(report: dict, run_number: int, started: dt.datetime, allowlist: dict, junit_b: dict, junit_f: dict,
               cov_b: dict, cov_f: dict, prior: list[dict], verdict: str) -> dict:
    summary = summarise(report)
    groups = skips.group(summary["tests"], allowlist)
    return history.build_record(
        run={"id": 34000000000 + run_number, "number": run_number, "attempt": 1, "sha": f"{run_number:07x}",
             "url": f"https://github.com/avivjan/BrrrrDealAnalyzer/actions/runs/{34000000000 + run_number}",
             "started": started.strftime("%Y-%m-%dT%H:%M:%SZ")},
        verdict=verdict,
        jobs={"ci": "success", "backend": "success", "frontend": "success", "playwright": "success" if verdict == "PASS" else "failure",
              "exit_code": "0" if verdict == "PASS" else "1"},
        summary=summary, skips_record=skips.to_record(groups), backend=junit_b, frontend=junit_f,
        coverage_backend=cov_b, coverage_frontend=cov_f, prior=prior)


def main() -> int:
    from nightly import coverage as cov_mod
    allowlist, err = skips.load_allowlist(HERE.parents[1] / "nightly" / "known_skips.json")
    assert not err, err
    rng = random.Random(20260906)
    now = dt.datetime(2026, 9, 6, 21, 3, 12, tzinfo=dt.timezone.utc)
    recurring = ("webkit", "flows/pdf-report.spec.ts", "exports a Flip PDF report")
    liquidity_key = ("chromium", "flows/liquidity.spec.ts", "settings, a one-off flow and a recurring series all persist")

    for variant in ("pass", "fail"):
        out = OUT / variant
        out.mkdir(parents=True, exist_ok=True)
        # 22 earlier runs.
        prior: list[dict] = []
        for i in range(22):
            started = now - dt.timedelta(days=22 - i)
            fails = {recurring} if i in (14, 17, 19) else set()
            slow = {liquidity_key: 1.0 + max(0, i - 17) * 0.12}  # drifts slower over the last 5 runs
            rep = build_report(random.Random(1000 + i), started, failures=fails, slow=slow)
            jb = junit.parse(_write(out / f"_hist_b{i}.xml", junit_backend(False, rng)))
            jf = junit.parse(_write(out / f"_hist_f{i}.xml", junit_frontend(rng)))
            cb = cov_mod.parse_pytest_cov_json(_write_json(out / f"_hist_cb{i}.json", coverage_backend(rng)))
            cf = cov_mod.parse_vitest_summary(_write_json(out / f"_hist_cf{i}.json", coverage_frontend(rng)))
            prior.append(record_for(rep, 30 + i, started, allowlist, jb, jf, cb, cf, prior, "FAIL" if fails else "PASS"))
        for p in out.glob("_hist_*"):
            p.unlink()
        (out / "history.jsonl").write_text("".join(json.dumps(r, separators=(",", ":"), sort_keys=True) + "\n" for r in prior))

        if variant == "pass":
            report = build_report(random.Random(4242), now, slow={liquidity_key: 1.55})
            _write(out / "backend-junit.xml", junit_backend(False, rng))
        else:
            report = build_report(
                random.Random(4343), now,
                failures={recurring, ("Mobile Safari", "flows/liquidity.spec.ts", "adds a one-off transaction")},
                flaky={("chromium", "flows/reps.spec.ts", "logs an activity with the timer")},
                unknown_skip=("Mobile Chrome", "flows/reps.spec.ts", "filters by month"),
                unannotated_skip=("webkit", "flows/landing.spec.ts", "the landing page links to Analyze"),
                zoom_skip=True, slow={liquidity_key: 2.1})
            _write(out / "backend-junit.xml", junit_backend(True, rng))
        _write_json(out / "report.json", report)
        _write(out / "frontend-junit.xml", junit_frontend(rng))
        _write_json(out / "backend-coverage.json", coverage_backend(rng))
        (out / "frontend-coverage").mkdir(exist_ok=True)
        _write_json(out / "frontend-coverage" / "coverage-summary.json", coverage_frontend(rng))
        print(f"{variant}: stats={report['stats']} history={len(prior)} runs -> {out}")
    return 0


def _write(path: pathlib.Path, text: str) -> pathlib.Path:
    path.write_text(text)
    return path


def _write_json(path: pathlib.Path, data: dict) -> pathlib.Path:
    path.write_text(json.dumps(data))
    return path


if __name__ == "__main__":
    sys.exit(main())
