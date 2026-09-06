"""Stdlib unit tests for the nightly email package.

    python3 -m unittest discover -s .github/scripts/nightly/tests -t .github/scripts
"""

from __future__ import annotations

import datetime as dt
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))

from nightly import anomalies, coverage, history, junit, skips  # noqa: E402
from nightly.playwright_report import normalize_file, summarise, test_key  # noqa: E402
from nightly.render_html import HTML_BUDGET  # noqa: E402

ALLOWLIST_PATH = HERE.parents[3] / ".github" / "nightly" / "known_skips.json"
ROOT = "/home/runner/work/BrrrrDealAnalyzer/BrrrrDealAnalyzer/frontend/e2e"


def _test(project, status, file, title, reason=None, duration=1000, retries=0):
    annotations = [{"type": "skip", "description": reason}] if reason else []
    results = [{"status": "skipped" if status == "skipped" else ("failed" if status == "unexpected" else "passed"),
                "duration": duration, "retry": 0, "annotations": annotations}]
    for r in range(retries):
        results.append({"status": "passed", "duration": duration, "retry": r + 1, "annotations": []})
    return {"projectName": project, "status": status, "annotations": annotations, "results": results}


def _report(tests_by_spec: dict[tuple[str, str], list[dict]], root=ROOT):
    suites = {}
    for (file, title), tests in tests_by_spec.items():
        suite = suites.setdefault(file, {"title": file, "file": file, "specs": [], "suites": []})
        suite["specs"].append({"title": title, "file": f"{root}/{file}", "tests": tests})
    stats = {"expected": 0, "unexpected": 0, "flaky": 0, "skipped": 0}
    for tests in tests_by_spec.values():
        for t in tests:
            stats[t["status"]] += 1
    return {"config": {"rootDir": root}, "suites": list(suites.values()), "errors": [],
            "stats": {"startTime": "2026-09-06T21:00:00Z", "duration": 60000, **stats}}


class NormalizeFile(unittest.TestCase):
    def test_strips_root_and_absolute_paths_like_compare_reports(self):
        self.assertEqual(normalize_file(f"{ROOT}/flows/x.spec.ts", ROOT), "flows/x.spec.ts")
        self.assertEqual(normalize_file("/Users/me/repo/frontend/e2e/checks/y.spec.ts", ""), "checks/y.spec.ts")
        self.assertEqual(normalize_file("./flows/z.spec.ts"), "flows/z.spec.ts")
        self.assertEqual(normalize_file("C:/x/frontend/e2e/flows/w.spec.ts"), "flows/w.spec.ts")
        self.assertEqual(normalize_file(""), "")

    def test_key_format_matches_compare_reports(self):
        self.assertEqual(test_key("webkit", "flows/x.spec.ts", "a > b"), "webkit :: flows/x.spec.ts :: a > b")


class Summarise(unittest.TestCase):
    def test_legacy_fields_and_new_fields(self):
        rep = _report({
            ("flows/a.spec.ts", "one"): [_test("chromium", "expected", "flows/a.spec.ts", "one", duration=3000),
                                         _test("webkit", "skipped", "flows/a.spec.ts", "one", reason="r")],
            ("flows/b.spec.ts", "two"): [_test("chromium", "flaky", "flows/b.spec.ts", "two", retries=1)],
        })
        s = summarise(rep)
        self.assertTrue(s["available"])
        self.assertEqual((s["passed"], s["failed"], s["skipped"], s["flaky"]), (1, 0, 1, 1))
        self.assertEqual(s["total_calls"], 4)  # one retry adds a call
        self.assertEqual(s["rerun_tests"], 1)
        self.assertEqual(s["per_project"]["webkit"], {"skipped": 1})
        self.assertIn("chromium :: flows/a.spec.ts :: one", s["tests_by_key"])
        self.assertEqual(s["tests_by_key"]["webkit :: flows/a.spec.ts :: one"]["skip_reasons"], ["r"])
        self.assertEqual(s["projects_present"], ["chromium", "webkit"])
        self.assertAlmostEqual(s["spec_file_ms"]["flows/a.spec.ts"], 3000)

    def test_missing_report(self):
        self.assertFalse(summarise(None)["available"])


class Allowlist(unittest.TestCase):
    def setUp(self):
        self.allowlist, err = skips.load_allowlist(ALLOWLIST_PATH)
        self.assertEqual(err, "")

    def test_every_catalogued_reason_matches(self):
        for reason in (
            "the axe baseline is recorded and replayed on chromium only",
            "performance entries are Chromium's; this test runs on chromium only",
            "performance entries are Chromium's; this test runs on chromium-motion only",
            "wheel emulation is Chromium-only",
            "no dist/ build to measure",
        ):
            self.assertIsNotNone(skips.match(reason, self.allowlist), reason)
        self.assertIsNone(skips.match("performance entries are Chromium's; this test runs on firefox only", self.allowlist))
        self.assertIsNone(skips.match("something new", self.allowlist))

    def test_expected_totals_sum_to_181_on_a_full_matrix(self):
        total = 0
        for entry in self.allowlist["reasons"]:
            total += sum((entry.get("expected") or {}).values())
        self.assertEqual(total, 181)

    def test_rules(self):
        axe = "the axe baseline is recorded and replayed on chromium only"
        tests = [
            _test("webkit", "skipped", "flows/a11y.spec.ts", "t", reason=axe),
            _test("webkit", "skipped", "flows/x.spec.ts", "u", reason="brand new reason"),
            _test("Mobile Chrome", "skipped", "flows/y.spec.ts", "v"),  # no annotation
            _test("Mobile Chrome", "skipped", "flows/liquidity.spec.ts", "w",
                  reason="the header overflows this device, so the page is zoomed out and its controls cannot be driven"),
        ]
        rep = _report({("flows/a11y.spec.ts", "t"): [tests[0]], ("flows/x.spec.ts", "u"): [tests[1]],
                       ("flows/y.spec.ts", "v"): [tests[2]], ("flows/liquidity.spec.ts", "w"): [tests[3]]})
        s = summarise(rep)
        groups = skips.group(s["tests"], self.allowlist)
        kinds = sorted(g["kind"] for g in groups)
        self.assertEqual(kinds, ["known", "known", "unannotated", "unknown"])
        found = skips.analyse(groups, self.allowlist, [], s["projects_present"], s["tests_by_key"], None)
        ids = sorted(a["id"] for a in found)
        # S5 (matrix differs, only 2 projects ran), S1 unknown, S2 unannotated, S3 zoomed-out fired
        self.assertEqual(ids, ["S1", "S2", "S3", "S5"])

    def test_s4_and_s6_on_a_full_matrix(self):
        axe = "the axe baseline is recorded and replayed on chromium only"
        projects = ["chromium", "webkit", "Mobile Safari", "Mobile Chrome", "chromium-motion"]
        specs = {("flows/p.spec.ts", f"t{i}"): [_test(p, "skipped" if p == "webkit" else "expected", "flows/p.spec.ts", f"t{i}",
                                                       reason=axe if p == "webkit" else None) for p in projects]
                 for i in range(18)}  # webkit skips 18 under a reason that expects 17
        s = summarise(_report(specs))
        groups = skips.group(s["tests"], self.allowlist)
        prev = {"playwright": {"skipped_keys": [], "failed": [], "flaky": [],
                               "durations": {"webkit :: flows/p.spec.ts :: t0": 1000}, "projects": {p: {} for p in projects}}}
        found = skips.analyse(groups, self.allowlist, [prev], s["projects_present"], s["tests_by_key"], prev)
        ids = [a["id"] for a in found]
        self.assertIn("S4a", ids)   # webkit 18 > 17
        self.assertIn("S4b", ids)   # Mobile Safari 0 < 17
        self.assertIn("S6", ids)    # t0 passed last night on webkit, skipped tonight
        self.assertNotIn("S5", ids)


class JUnit(unittest.TestCase):
    def test_pytest_and_vitest_shapes(self):
        with tempfile.TemporaryDirectory() as d:
            p = pathlib.Path(d) / "b.xml"
            p.write_text('<?xml version="1.0"?><testsuites><testsuite name="pytest" tests="3" time="2.5">'
                         '<testcase classname="tests.test_a" name="ok" time="0.5"/>'
                         '<testcase classname="tests.test_a" name="bad" time="1.5"><failure message="boom">x</failure></testcase>'
                         '<testcase classname="tests.test_b" name="skip" time="0"><skipped message="why"/></testcase>'
                         '</testsuite></testsuites>')
            s = junit.parse(p)
            self.assertTrue(s["available"])
            self.assertEqual((s["tests"], s["failures"], s["errors"], s["skipped"], s["passed"]), (3, 1, 0, 1, 1))
            self.assertEqual(s["time_s"], 2.5)
            self.assertEqual(s["slowest"][0]["name"], "bad")
            self.assertEqual(s["failed"][0]["message"], "boom")
            v = pathlib.Path(d) / "v.xml"
            v.write_text('<testsuites name="vitest tests" tests="1" time="3"><testsuite name="src/x.test.ts" tests="1">'
                         '<testcase classname="src/x.test.ts" name="c" time="0.01"/></testsuite></testsuites>')
            self.assertEqual(junit.parse(v)["by_file"]["src/x.test.ts"]["tests"], 1)
        self.assertEqual(junit.parse(pathlib.Path(d) / "missing.xml")["error"], "artifact missing")
        self.assertFalse(junit.parse(None)["available"])


class Coverage(unittest.TestCase):
    def test_parsers_and_status(self):
        with tempfile.TemporaryDirectory() as d:
            b = pathlib.Path(d) / "b.json"
            b.write_text(json.dumps({"files": {"a.py": {"summary": {"percent_covered": 20.0, "num_statements": 50}},
                                               "tiny.py": {"summary": {"percent_covered": 0.0, "num_statements": 3}}},
                                     "totals": {"percent_covered": 70.5}}))
            cb = coverage.parse_pytest_cov_json(b)
            self.assertEqual(cb["pct"], 70.5)
            self.assertEqual([f[0] for f in cb["lowest"]], ["a.py"])  # tiny.py is under the statement floor
            f = pathlib.Path(d) / "f.json"
            f.write_text(json.dumps({"total": {"lines": {"pct": 61.2}},
                                     "/x/frontend/src/a.ts": {"lines": {"total": 40, "covered": 10, "pct": 25.0}}}))
            cf = coverage.parse_vitest_summary(f)
            self.assertEqual(cf["lowest"][0][0], "src/a.ts")
            self.assertEqual(coverage.status(cb, cf), "wired")
            self.assertEqual(coverage.status(cb, coverage.parse_vitest_summary(None)), "partial")
        self.assertEqual(coverage.status(coverage.parse_pytest_cov_json(None), coverage.parse_vitest_summary(None)), "not_wired")


class History(unittest.TestCase):
    def test_tail_append_and_malformed_lines(self):
        with tempfile.TemporaryDirectory() as d:
            p = pathlib.Path(d) / "history.jsonl"
            p.write_text('{"v":1,"run":{"started":"2026-09-01T21:00:00Z"},"playwright":{"projects":{"chromium":{}}}}\n'
                         'not json\n{"v":9}\n')
            recs, malformed = history.load_tail(p, 30)
            self.assertEqual((len(recs), malformed), (1, 2))
            history.append(p, {"v": 1, "run": {"started": "2026-09-02T21:00:00Z"}, "playwright": {"projects": {"chromium": {}}}})
            recs, _ = history.load_tail(p, 30)
            self.assertEqual(len(recs), 2)
            self.assertEqual(history.load_tail(p, 1)[0][0]["run"]["started"], "2026-09-02T21:00:00Z")
        self.assertEqual(history.load_tail(pathlib.Path(d) / "nope.jsonl"), ([], 0))

    def test_same_matrix_previous_and_week_ago(self):
        mk = lambda day, projects: {"v": 1, "source": "nightly", "run": {"started": f"2026-09-{day:02d}T21:00:00Z"},
                                    "playwright": {"projects": {p: {} for p in projects}}}
        prior = [mk(1, ["chromium"]), mk(2, ["chromium", "webkit"]), mk(8, ["chromium", "webkit"])]
        tonight = mk(9, ["chromium", "webkit"])
        self.assertEqual(history.previous(prior, tonight)["run"]["started"], "2026-09-08T21:00:00Z")
        now = dt.datetime(2026, 9, 9, 21, tzinfo=dt.timezone.utc)
        self.assertEqual(history.week_ago(prior, tonight, now)["run"]["started"], "2026-09-02T21:00:00Z")
        self.assertEqual(history.comparable(prior, tonight), prior[1:])


class Anomalies(unittest.TestCase):
    def _rec(self, day, durations, failed=(), flaky=()):
        return {"v": 1, "source": "nightly", "run": {"started": f"2026-09-{day:02d}T21:00:00Z"},
                "playwright": {"projects": {"chromium": {}}, "durations": durations, "failed": list(failed), "flaky": list(flaky),
                               "stats": {"expected": 10, "unexpected": len(failed), "skipped": 0, "duration_ms": 60000}}}

    def test_slow_regression_needs_three_samples_and_absolute_delta(self):
        prior = [self._rec(d, {"k": 1000}) for d in range(1, 8)]
        self.assertEqual(anomalies.slow_regressions(self._rec(8, {"k": 1600}), prior), {})   # ratio 1.6 but delta < 2 s
        prior = [self._rec(d, {"k": 10000}) for d in range(1, 8)]
        self.assertIn("k", anomalies.slow_regressions(self._rec(8, {"k": 16000}), prior))
        self.assertEqual(anomalies.slow_regressions(self._rec(8, {"k": 16000}), prior[:2]), {})  # only 2 samples

    def test_first_seen_vs_recurring_and_flaky(self):
        prior = [self._rec(d, {"a": 1000, "b": 1000}, failed=["b"] if d in (3, 5) else []) for d in range(1, 8)]
        tonight = self._rec(8, {"a": 1000, "b": 1000}, failed=["a", "b"], flaky=["c"])
        classes = anomalies.failure_classes(tonight, prior)
        self.assertTrue(classes["a"]["first_seen"])
        self.assertEqual(classes["b"]["recurring"], 2)
        flaky = anomalies.flaky_tests(tonight, prior)
        self.assertIn("c", [f["key"] for f in flaky])
        self.assertIn("b", [f["key"] for f in flaky])  # flipped ok/bad/ok/bad/... ≥2 times

    def test_deltas_and_first_run(self):
        tonight = self._rec(8, {"a": 1000})
        self.assertIsNone(anomalies.tile_deltas(tonight, None, None)["passed"]["vs_prev"])
        prev = self._rec(7, {"a": 1000})
        prev["playwright"]["stats"]["expected"] = 8
        self.assertEqual(anomalies.tile_deltas(tonight, prev, None)["passed"]["vs_prev"]["word"], "up 2")


class EndToEnd(unittest.TestCase):
    """The CLI renders the preview fixtures; every legacy line is present; the HTML stays under budget."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        env = {**os.environ, "CI_OUTCOME": "success", "BACKEND_OUTCOME": "success", "FRONTEND_OUTCOME": "success",
               "E2E_OUTCOME": "failure", "E2E_EXIT_CODE": "1", "RUN_URL": "https://example.test/run/1"}
        script = HERE.parents[1] / "nightly_e2e_email.py"
        subprocess.run([sys.executable, str(HERE.parent / "make_preview_fixtures.py")], check=True, capture_output=True,
                       env={**env, "PYTHONDONTWRITEBYTECODE": "1"})
        cls.out = HERE.parent / "out" / "fail"
        cls.html = pathlib.Path(cls.tmp.name) / "mail.html"
        cls.text = pathlib.Path(cls.tmp.name) / "mail.txt"
        cls.record = pathlib.Path(cls.tmp.name) / "record.json"
        result = subprocess.run([
            sys.executable, str(script), "--playwright", str(cls.out / "report.json"),
            "--backend-junit", str(cls.out / "backend-junit.xml"), "--frontend-junit", str(cls.out / "frontend-junit.xml"),
            "--backend-coverage", str(cls.out / "backend-coverage.json"),
            "--frontend-coverage", str(cls.out / "frontend-coverage" / "coverage-summary.json"),
            "--history", str(cls.out / "history.jsonl"), "--write-record", str(cls.record),
            "--write-html", str(cls.html), "--write-text", str(cls.text), "--no-send", "--charts", "table",
            "--now", "2026-09-06T21:05:00Z",
        ], capture_output=True, text=True, env=env)
        cls.result = result

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_runs_and_writes_everything(self):
        self.assertEqual(self.result.returncode, 0, self.result.stderr)
        self.assertTrue(self.html.exists() and self.text.exists() and self.record.exists())

    def test_legacy_lines_present(self):
        text = self.text.read_text()
        for line in ("Test Session Report", "Session finished with exit code 1 (Failures present)", "Total test calls (run): ",
                     "Test Outcomes:", "  Passed: ", "  Failed: 2", "  Skipped: ", "test(s) were rerun (1 flaky).",
                     "Results by browser:", "Failed tests (2):", "Longest-Running Tests:", "Some checks failed.",
                     "Run and HTML report artifact: https://example.test/run/1"):
            self.assertIn(line, text, line)

    def test_new_sections_and_anomalies(self):
        text = self.text.read_text()
        for line in ("Anomalies:", "Skipped by reason", "Backend and frontend suites", "Trends", "Coverage gaps",
                     "UNKNOWN REASON", "NO SKIP ANNOTATION", "[first seen]", "[recurring,", "SHOULD NEVER FIRE",
                     "slower than usual"):
            self.assertIn(line, text, line)
        record = json.loads(self.record.read_text())
        self.assertEqual(record["v"], 1)
        self.assertEqual(record["playwright"]["stats"]["unexpected"], 2)
        self.assertNotIn("/home/", json.dumps(record))

    def test_html_budget_and_tokens(self):
        html = self.html.read_text()
        self.assertLess(len(html), HTML_BUDGET)
        self.assertIn("#7d5f27", html)   # luxury accent
        self.assertNotIn("#dc2626", html)  # no v1 alarm red
        self.assertNotIn("/home/runner", html)


if __name__ == "__main__":
    unittest.main()
