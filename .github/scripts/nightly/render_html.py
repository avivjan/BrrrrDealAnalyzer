"""HTML body in the site's quiet-luxury look. Every v1 metric and line is still present."""

from __future__ import annotations

from . import theme as T, junit
from .playwright_report import test_label
from .render_text import fmt_secs

e = T.e

HTML_BUDGET = 95_000  # Gmail clips around 102 KB; lists below are capped to stay under this


def fmt_minutes(ms: float) -> str:
    return f"{ms / 1000 / 60:.1f} min"


SUITE_NAMES = {"playwright": "Playwright", "backend": "Backend (pytest)", "frontend": "Frontend (vitest)"}


def _suite_parts_line(parts: dict) -> str:
    """'Playwright 420 · Backend (pytest) 118 · Frontend (vitest) 1368', a missing suite says so."""
    bits = []
    for key, name in SUITE_NAMES.items():
        part = parts.get(key) or {}
        if part.get("available"):
            bits.append(f'{e(name)} <b style="color:{T.INK};">{part["total"]}</b>'
                        + (f' <span style="color:{T.NEGATIVE};">({part["failed"]} failed)</span>' if part["failed"] else ""))
        else:
            bits.append(f"{e(name)} no report")
    return "Tests by suite: " + " · ".join(bits)


def _delta_lines(deltas: dict | None, up_is_good: bool | None) -> list[tuple[str, str]]:
    """Tile delta lines: (text, tone). Tone = direction × whether up is good; None → neutral."""
    if not deltas:
        return []
    out = []
    for label, d in (("vs last run", deltas.get("vs_prev")), ("vs 7 days ago", deltas.get("vs_week"))):
        if d is None:
            continue
        diff = d["diff"]
        if diff == 0:
            out.append((f"no change {label}", "neutral"))
            continue
        arrow = "▲" if diff > 0 else "▼"
        if up_is_good is None:
            tone = "neutral"
        else:
            good = (diff > 0) == up_is_good
            tone = "positive" if good else "warning"
        out.append((f"{arrow} {abs(diff):g} {label}", tone))
    return out


def render_html(ctx: dict, image_cids: dict[str, str]) -> str:
    s = ctx["summary"]
    a = ctx["analysis"]
    ok = ctx["verdict"] == "PASS"
    findings = a["findings"]
    deltas = a["deltas"] or {}

    # --- header ---------------------------------------------------------------
    verdict_pill = T.pill(ctx["verdict"], "positive" if ok else "negative")
    header = (
        f'<tr><td style="padding:30px 32px 8px 32px;">'
        f'{T.eyebrow("BrrrrDealAnalyzer · Nightly test session")}'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>'
        f'<td style="padding-top:10px;">{T.display(e(ctx["bottom_line"]["title"]), 28, 600)}</td>'
        f'<td align="right" valign="top" style="padding-top:12px;">{verdict_pill}</td></tr></table>'
        f'<div style="margin-top:8px;">{T.body_text(e(ctx["bottom_line"]["detail"]), 15)}</div>'
        f'<div style="margin-top:6px;">{T.body_text(e(ctx["headline"]) + " · " + e(ctx["when"]), 13, T.MUTED)}</div>'
        f'</td></tr>'
    )

    # --- tiles -----------------------------------------------------------------
    totals = ctx["totals"]
    tiles = "".join([
        T.tile("Passed", totals["passed"], _delta_lines(deltas.get("passed"), True)),
        T.tile("Failed", totals["failed"], _delta_lines(deltas.get("failed"), False)),
        T.tile("Skipped", totals["skipped"], _delta_lines(deltas.get("skipped"), None)),
        T.tile("Tests, all suites", totals["total"], _delta_lines(deltas.get("total"), None)),
    ])
    tiles_row = (
        f'<tr><td style="padding:14px 26px 0 26px;">'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>{tiles}</tr></table></td></tr>'
        f'<tr><td style="padding:8px 32px 6px 32px;">{T.note(_suite_parts_line(totals["parts"]))}</td></tr>'
    )

    # --- anomalies -------------------------------------------------------------
    if findings:
        rows = "".join(
            T.row(
                f'{T.pill(f["severity"], T.severity_tone(f["severity"]))}&nbsp;&nbsp;'
                f'<span style="font:500 14px {T.BODY};color:{T.INK};">{e(f["title"])}</span>'
                f'<div style="font:12px {T.MONO};color:{T.MUTED};margin-top:3px;overflow-wrap:anywhere;">{e(f["detail"])}</div>',
                f'<span style="font:12px {T.BODY};color:{T.MUTED};">{e(f["section"])}</span>',
                last=(i == len(findings) - 1),
            )
            for i, f in enumerate(findings[:30])
        )
        more = T.note(f"… and {len(findings) - 30} more") if len(findings) > 30 else ""
        counts = {}
        for f in findings:
            counts[f["severity"]] = counts.get(f["severity"], 0) + 1
        marker = "&nbsp;".join(T.pill(f"{n} {sev}", T.severity_tone(sev)) for sev, n in counts.items())
        anomalies_block = T.section("Anomalies", T.table(rows) + more, marker)
    else:
        anomalies_block = T.section("Anomalies", T.table(T.row(
            T.note(f"None against the allow-list or the last {ctx['history']['count']} run(s). Every skip below is expected."),
            T.pill("all clear", "positive"), last=True)))

    # --- session report (legacy lines verbatim) ---------------------------------
    exit_code = ctx["exit_code"]
    if s["available"]:
        session_line = (f"Session finished with exit code {exit_code} "
                        f"({'All tests passed' if s['failed'] == 0 and str(exit_code) == '0' else 'Failures present'})")
        duration_line = f"Playwright wall-clock: {fmt_minutes(s['duration_ms'])}"
        if a["wall"]:
            duration_line += f" · {a['wall']['ratio']:.2f}× the 7-run median"
    else:
        session_line = f"No Playwright JSON report was produced (job result: {ctx['e2e_outcome']}, exit code {exit_code})"
        duration_line = ""
    rerun_line = ("No tests were rerun." if s["rerun_tests"] == 0
                  else f"{s['rerun_tests']} test(s) were rerun ({s['flaky']} flaky).")
    outcomes = (f"Test outcomes: Passed {s['passed']} · Failed {s['failed']} · Skipped {s['skipped']}")
    session_rows = [
        (T.mono(e(session_line)), ""),
        (T.mono(f"Total test calls (run): <b>{s['total_calls']}</b>"), ""),
        (T.mono(e(outcomes)), T.pill("failures", "negative") if s["failed"] else ""),
        (T.mono(e(rerun_line)), T.pill("reruns", "warning") if s["rerun_tests"] else ""),
    ]
    if duration_line:
        session_rows.append((T.mono(e(duration_line), colour=T.MUTED), T.pill("slow", "warning") if a["wall"] and a["wall"]["slow"] else ""))
    session_block = T.section("Playwright session report", T.table("".join(
        T.row(l, r, last=(i == len(session_rows) - 1)) for i, (l, r) in enumerate(session_rows))))

    # --- jobs ---------------------------------------------------------------------
    jobs_block = T.section("Jobs", T.table("".join(
        T.row(e(label), T.pill(outcome, T.outcome_tone(outcome)), last=(i == len(ctx["jobs"]) - 1))
        for i, (label, outcome) in enumerate(ctx["jobs"]))))

    # --- results by browser ----------------------------------------------------------
    if s["per_project"]:
        head = "<tr>" + T.th("Browser project") + "".join(T.th(h, "center") for h in ("Passed", "Failed", "Flaky", "Skipped")) + "</tr>"
        body = ""
        for project, counts in s["per_project"].items():
            cells = ""
            for key, tone in (("expected", None), ("unexpected", "negative"), ("flaky", "warning"), ("skipped", None)):
                n = counts.get(key, 0)
                colour = T.INK if n else T.MUTED
                weight = 600 if n else 400
                cell = T.mono(str(n), 13, colour, weight)
                if n and tone:
                    cell += f"&nbsp;{T.pill(key if key != 'unexpected' else 'failed', tone)}"
                cells += T.td(cell, "center")
            body += "<tr>" + T.td(f'<span style="font:13px {T.BODY};color:{T.INK};">{e(project)}</span>') + cells + "</tr>"
        browser_block = T.section("Results by browser", T.table(head + body))
    else:
        browser_block = T.section("Results by browser", T.note("No per-browser data."))

    # --- failed tests --------------------------------------------------------------------
    failed_block = ""
    if s["failed_tests"]:
        rows = ""
        for i, t in enumerate(s["failed_tests"][:40]):
            cls = a["failure_classes"].get(t["key"])
            tag = ""
            if cls:
                tag = T.pill("first seen", "negative") if cls["first_seen"] else T.pill(f"recurring · {cls['recurring']} of {cls['window']}", "warning")
            rows += T.row(
                f'{T.pill("failed", "negative")}&nbsp; <span style="font:12px {T.MONO};color:{T.INK};">'
                f'<span style="color:{T.MUTED};">[{e(t["project"])}]</span> {e(test_label(t))}</span>',
                tag, last=(i == min(len(s["failed_tests"]), 40) - 1))
        more = T.note(f"… and {len(s['failed_tests']) - 40} more") if len(s["failed_tests"]) > 40 else ""
        failed_block = T.section(f"Failed tests ({len(s['failed_tests'])})", T.table(rows) + more)

    # --- backend & frontend suites ----------------------------------------------------------
    suites_block = T.section("Backend, MCP and frontend suites", _suites_html(ctx))

    # --- skipped by reason ---------------------------------------------------------------------
    skips_block = T.section("Skipped by reason", _skips_html(ctx),
                            T.pill(f"{s['skipped']} skipped", "neutral") if s["available"] else "")

    # --- trends -----------------------------------------------------------------------------------
    trends_block = T.section("Trends", _trends_html(ctx, image_cids),
                             T.pill(f"{ctx['history']['count']} run(s) on record", "neutral"))

    # --- top N longest ------------------------------------------------------------------------------
    top_rows = ""
    max_ms = max((t["duration_ms"] for t in s["top"]), default=1) or 1
    for i, t in enumerate(s["top"], 1):
        pct = max(2, int(round(100 * t["duration_ms"] / max_ms)))
        slow = a["slow"].get(t["key"])
        tag = ""
        if t["status"] == "unexpected":
            tag = T.pill("failed", "negative")
        elif t["status"] == "flaky":
            tag = T.pill("flaky", "warning")
        if slow:
            tag += ("&nbsp;" if tag else "") + T.pill(f"slower than usual · {slow['ratio']:.1f}×", "warning")
        top_rows += (
            "<tr>"
            + T.td(T.mono(str(i), 12, T.MUTED), "right")
            + T.td(f'<span style="font:12px {T.MONO};color:{T.INK};overflow-wrap:anywhere;">'
                   f'<span style="color:{T.MUTED};">[{e(t["project"])}]</span> {e(test_label(t))}</span>'
                   + (f'<div style="margin-top:3px;">{tag}</div>' if tag else ""))
            + T.td(T.bar(pct, "accent"), "left", "width:130px;")
            + T.td(T.mono(fmt_secs(t["duration_ms"]), 12, T.INK, 600), "right", "white-space:nowrap;")
            + "</tr>"
        )
    top_block = T.section(f"Top {len(s['top'])} longest-running tests",
                          T.table(top_rows) if top_rows else T.note("No timing data."))

    # --- spec files -------------------------------------------------------------------------------------
    files_block = ""
    if a["spec_files"]:
        rows = ""
        for i, r in enumerate(a["spec_files"]):
            trend = {"up": ("▲ slower", "warning"), "down": ("▼ faster", "positive"), "steady": ("steady", "neutral"),
                     "no history": ("no history yet", "neutral")}[r["trend"]]
            extra = f" · median {r['median_ms'] / 1000:.1f}s" if r["median_ms"] else ""
            rows += T.row(
                f'<span style="font:12px {T.MONO};color:{T.INK};">{e(r["file"])}</span>'
                f'<span style="font:12px {T.BODY};color:{T.MUTED};"> · {r["ms"] / 1000:.1f}s{extra}</span>',
                T.pill(*trend), last=(i == len(a["spec_files"]) - 1))
        files_block = T.section("Longest-running spec files", T.table(rows))

    # --- coverage ---------------------------------------------------------------------------------------------
    coverage_block = T.section("Coverage gaps", _coverage_html(ctx))

    # --- closing --------------------------------------------------------------------------------------------------
    closing_text = "All tests passed! Well done." if ok else "Some checks failed. See the details above and the run link below."
    closing = (
        f'<tr><td style="padding:24px 32px 30px 32px;">'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-top:1px solid {T.LINE};"><tr>'
        f'<td style="padding-top:18px;">{T.display(e(closing_text), 18, 600)}</td></tr></table>'
        f'<div style="font:12px {T.BODY};color:{T.MUTED};margin-top:12px;">'
        f'<a href="{e(ctx["run_url"])}" style="color:{T.ACCENT};text-decoration:none;font-weight:600;">Open the workflow run</a>'
        f' &nbsp;·&nbsp; the Playwright HTML report and traces are attached to it as an artifact.'
        f'</div></td></tr>'
    )

    body = (
        f'<div style="background:{T.PAGE};padding:28px 12px;">'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr><td align="center">'
        f'<table role="presentation" width="700" cellpadding="0" cellspacing="0" '
        f'style="max-width:700px;width:100%;background:{T.CARD};border-radius:16px;border:1px solid {T.LINE};box-shadow:{T.SHADOW_1};">'
        + header + tiles_row + anomalies_block + session_block + jobs_block + browser_block + failed_block
        + suites_block + skips_block + trends_block + top_block + files_block + coverage_block + closing
        + "</table></td></tr></table></div>"
    )
    return f'<!doctype html><html><body style="margin:0;padding:0;background:{T.PAGE};">{body}</body></html>'


def _suites_html(ctx: dict) -> str:
    cols = ""
    for name, sub, suite in (("Backend", "pytest + Postgres", ctx["junit"]["backend"]),
                             ("MCP server", "tests/test_mcp*, from the backend run", ctx["junit"].get("mcp", junit.parse(None))),
                             ("Frontend", "vitest", ctx["junit"]["frontend"])):
        inner = T.label(f"{name} · {sub}")
        if not suite["available"]:
            inner += T.note(e(suite["error"] or "no report")) + T.body_text("&nbsp;", 12)
        else:
            failed_n = suite["failures"] + suite["errors"]
            inner += (
                f'<div style="margin-top:8px;">{T.display(str(suite["passed"]), 24)}'
                f'<span style="font:12px {T.BODY};color:{T.MUTED};"> passed of {suite["tests"]} '
                f'· {suite["time_s"]:.1f}s</span></div>'
                f'<div style="margin-top:6px;">'
                + (T.pill(f"{failed_n} failed", "negative") + "&nbsp;" if failed_n else T.pill("0 failed", "neutral") + "&nbsp;")
                + T.pill(f"{suite['skipped']} skipped", "neutral") + "</div>"
            )
            if suite["failed"]:
                inner += '<div style="margin-top:10px;">' + T.label("failing") + "".join(
                    f'<div style="font:11px {T.MONO};color:{T.INK};margin-top:4px;overflow-wrap:anywhere;">{e(c["classname"])}::{e(c["name"])}</div>'
                    for c in suite["failed"][:8]) + "</div>"
            inner += '<div style="margin-top:10px;">' + T.label("slowest") + "".join(
                f'<div style="font:11px {T.MONO};color:{T.INK};margin-top:4px;overflow-wrap:anywhere;">'
                f'<span style="color:{T.MUTED};">{c["time_s"]:.2f}s</span> {e(c["name"])}'
                f'<span style="color:{T.MUTED};"> · {e(c["classname"].split("/")[-1][:40])}</span></div>'
                for c in suite["slowest"][:5]) + "</div>"
        cols += f'<td width="33%" valign="top" style="padding:0 8px 0 0;">{inner}</td>'
    return f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>{cols}</tr></table>'


def _skips_html(ctx: dict) -> str:
    groups = ctx["skips"]["groups"]
    s = ctx["summary"]
    if not s["available"]:
        return T.note("No Playwright report, so nothing to classify.")
    if not groups:
        return T.note("No skipped tests tonight.")
    routine = [g for g in groups if g["kind"] == "known" and g["entry"].get("expected_total") != 0]
    flagged = [g for g in groups if g not in routine]
    out = ""
    if flagged:
        rows = ""
        for i, g in enumerate(flagged):
            if g["kind"] == "unannotated":
                title, tone, reason = "No skip annotation", "negative", "fixture or beforeAll failed before the test body ran"
            elif g["kind"] == "unknown":
                title, tone, reason = "Unknown reason", "negative", g["reason"]
            else:
                title, tone, reason = f"Should never fire · {g['entry']['id']}", "negative", g["reason"]
            rows += T.row(
                f'{T.pill(title, tone)}<div style="font:12px {T.MONO};color:{T.INK};margin-top:4px;">{e(reason)}</div>'
                f'<div style="font:12px {T.BODY};color:{T.MUTED};margin-top:2px;">{_projects(g["by_project"])}</div>',
                T.mono(str(g["total"]), 14, T.INK, 600), last=(i == len(flagged) - 1))
        out += T.label("Needs a look") + T.table(rows) + '<div style="height:14px;"></div>'
    if routine:
        rows = ""
        for i, g in enumerate(routine):
            entry = g["entry"]
            exp = entry.get("expected") or {}
            expected_total = sum(exp.values()) if exp else None
            match_pill = ""
            if expected_total is not None:
                match_pill = (T.pill(f"expected {expected_total} · observed {g['total']}", "neutral")
                              if expected_total == g["total"] else
                              T.pill(f"expected {expected_total} · observed {g['total']}", "warning"))
            rows += T.row(
                f'<span style="font:600 13px {T.BODY};color:{T.INK};">{e(entry["category"])}</span>'
                f'<div style="font:12px {T.MONO};color:{T.MUTED};margin-top:3px;">“{e(g["reason"])}”</div>'
                f'<div style="font:13px {T.BODY};color:{T.INK};margin-top:5px;line-height:1.5;">{e(entry.get("explain", ""))}</div>'
                f'<div style="font:12px {T.BODY};color:{T.MUTED};margin-top:4px;">{_projects(g["by_project"])}</div>'
                + (f'<div style="margin-top:6px;">{match_pill}</div>' if match_pill else ""),
                T.mono(str(g["total"]), 16, T.INK, 600), last=(i == len(routine) - 1))
        out += T.label("Expected, by design") + T.table(rows)
    return out


def _projects(by_project: dict) -> str:
    return " · ".join(f"{e(p)} {n}" for p, n in by_project.items())


def _trends_html(ctx: dict, image_cids: dict[str, str]) -> str:
    if ctx["history"]["count"] == 0:
        return T.note("First run: history starts today. Charts appear once two or more nightly runs are on record.")
    out = ""
    for name, alt in (("pass_fail", "Passed, failed and skipped per run"),
                      ("skips", "Skipped tests per run by category"),
                      ("slowest", "Tonight's slowest tests over recent runs")):
        cid = image_cids.get(name)
        if cid:
            out += (f'<div style="margin:0 0 14px 0;"><img src="cid:{cid}" width="640" height="220" alt="{e(alt)}" '
                    f'style="display:block;width:100%;max-width:640px;height:auto;border:1px solid {T.LINE};border-radius:8px;"></div>')
    if not out:
        rows = ""
        for i, r in enumerate(ctx["trend_rows"][-10:]):
            rows += T.row(
                T.mono(f"{r['label']} · #{r['number']} · {r['passed']} passed · {r['failed']} failed · {r['skipped']} skipped · {r['minutes']:.1f} min", 12),
                T.pill(r["verdict"], "positive" if r["verdict"] == "PASS" else "negative"), last=(i == min(len(ctx["trend_rows"]), 10) - 1))
        out = T.note(ctx["history"]["chart_note"]) + T.table(rows)
    return out


def _coverage_html(ctx: dict) -> str:
    cov = ctx["coverage"]
    if cov["status"] == "not_wired":
        steps = "".join(f'<li style="margin:4px 0;">{e(step)}</li>' for step in cov["steps"])
        return (T.note("Coverage is not wired yet. To light this section up:")
                + f'<ol style="font:13px {T.BODY};color:{T.INK};padding-left:20px;margin:8px 0 0 0;">{steps}</ol>')
    cols = ""
    for name, c in (("Backend", cov["backend"]), ("Frontend", cov["frontend"])):
        inner = T.label(name)
        if not c["available"]:
            inner += T.note(e(c["error"] or "no coverage report"))
        else:
            pct = f"{c['pct']:.1f}%" if c["pct"] is not None else "n/a"
            inner += f'<div style="margin-top:8px;">{T.display(pct, 24)}<span style="font:12px {T.BODY};color:{T.MUTED};"> line coverage</span></div>'
            inner += '<div style="margin-top:10px;">' + T.label("lowest-covered modules")
            for path, v, n in c["lowest"]:
                inner += (f'<div style="margin-top:6px;"><div style="font:11px {T.MONO};color:{T.INK};overflow-wrap:anywhere;">{e(path)}</div>'
                          f'<table role="presentation" cellpadding="0" cellspacing="0"><tr><td>{T.bar(int(v), "accent2", 120)}</td>'
                          f'<td style="padding-left:8px;">{T.mono(f"{v:.0f}%", 11, T.MUTED)}</td></tr></table></div>')
            inner += "</div>"
        cols += f'<td width="33%" valign="top" style="padding:0 8px 0 0;">{inner}</td>'
    return f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>{cols}</tr></table>'
