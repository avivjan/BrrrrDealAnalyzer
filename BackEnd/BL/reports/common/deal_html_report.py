"""Big Whales interactive deal report: one self-contained HTML file that works like the website's
calculation breakdown popups.

Why HTML: every phone and computer opens it with the browser it already has (iPhone, Mac, Windows,
Galaxy, ...), it travels as an ordinary attachment on WhatsApp and Gmail, and it needs no account,
no app and no network: the styles, the logo and the script are inline, and nothing is fetched.

Why it works with JavaScript off: the iPhone preview that opens a file from WhatsApp or Mail, and
the app's own preview frame, run without scripts. The popup's drill-down is therefore built from
native `<details>` / `<summary>` elements, which expand and collapse in place with no script. The
small inline script only adds "Expand all" / "Collapse all" and the light/dark switch where it may run.

The content is the popup's, row for row: the rows come from `breakdown_tree` (the port of the popup's
`calculationBreakdownTree.ts`, pinned to it by a shared parity fixture) and every value is formatted by
`format_value_like_calculation_popup` (the port of `calculationStepFormat.ts`). Each chosen result is a
card laid out like `CalculationBreakdownPopup.vue`: the answer first, the first level open, every
computed row expandable down to the raw inputs, "Derived from this" and "All N steps in calculation
order". Every piece of text goes through `escape`, and the file's own Content-Security-Policy lets it
run nothing but its one script and load nothing at all.
"""

from __future__ import annotations

import base64
import hashlib
from dataclasses import dataclass
from datetime import datetime
from html import escape
from typing import Any, Optional

from BL.reports.common.breakdown_tree import (
    CalculationBreakdownRow,
    child_ancestor_step_labels,
    find_headline_step_index,
    is_sum_step,
    rows_of_step,
    rows_of_steps,
    steps_after_headline,
    top_level_rows_for_headline,
)
from BL.reports.common.deal_pdf import format_value_like_calculation_popup
from BL.reports.common.report_result_tiles import ReportResultTile, select_report_result_tiles


@dataclass
class _HtmlReportResultSection:
    result_index: int
    tile: ReportResultTile
    steps: list[dict]
    headline_step: Optional[dict]
    top_level_rows: list[CalculationBreakdownRow]
    derived_rows: list[CalculationBreakdownRow]

    @property
    def title(self) -> str:
        return f"How {self.tile.tile_label} is calculated"

    @property
    def anchor_id(self) -> str:
        # Named from the index only, never from text.
        return f"result-{self.result_index}"

    @property
    def root_ancestor_step_labels(self) -> frozenset[str]:
        return frozenset({self.headline_step["label"]}) if self.headline_step else frozenset()


def _build_html_report_result_section(result_index: int, tile: ReportResultTile, result: dict, breakdowns: dict) -> _HtmlReportResultSection:
    steps = breakdowns.get(tile.result_key) or []
    headline_step_index = find_headline_step_index(steps, result.get(tile.result_key))
    return _HtmlReportResultSection(
        result_index=result_index,
        tile=tile,
        steps=steps,
        headline_step=steps[headline_step_index] if headline_step_index >= 0 else None,
        top_level_rows=top_level_rows_for_headline(breakdowns, tile.result_key, headline_step_index),
        derived_rows=rows_of_steps(steps_after_headline(steps, headline_step_index), "derived"),
    )


def _text(value: Any) -> str:
    return escape("" if value is None else str(value), quote=True)


def _formatted(unit: Optional[str], value: Any) -> str:
    return _text(format_value_like_calculation_popup(unit, value))


# -- the popup's tree as nested <details> ----------------------------------------------------------
def _row_line_markup(row: CalculationBreakdownRow, is_expandable: bool) -> str:
    chevron = '<span class="chev" aria-hidden="true"></span>' if is_expandable else '<span class="chev-space" aria-hidden="true"></span>'
    return (
        f'{chevron}<span class="sign">{_text(row.sign or "")}</span>'
        f'<span class="label">{_text(row.label)}</span>'
        f'<span class="val">{_formatted(row.unit, row.value)}</span>'
    )


def _total_line_markup(label: str, unit: Optional[str], value: Any, css_class: str = "total") -> str:
    return (
        f'<li class="{css_class}"><span class="chev-space" aria-hidden="true"></span><span class="sign">=</span>'
        f'<span class="label">{_text(label)}</span><span class="val">{_formatted(unit, value)}</span></li>'
    )


def _rows_markup(
    rows: list[CalculationBreakdownRow],
    breakdowns: dict,
    section_key: str,
    ancestor_step_labels: frozenset[str],
    depth: int,
) -> str:
    """Rows as the popup draws them. A row the popup can expand is a `<details>` holding its own rows
    (ending on "= step") or its formula, then its note, recursively down the whole tree; the first
    level starts open, as the popup does on arrival."""
    parts: list[str] = []
    for row in rows:
        if row.linked_step is None:
            parts.append(f'<li class="row leaf" data-depth="{depth}"><div class="line">{_row_line_markup(row, False)}</div></li>')
            continue
        children_ancestors = child_ancestor_step_labels(row, ancestor_step_labels)
        children = rows_of_step(row.linked_step, breakdowns, section_key, row.path, children_ancestors)
        if children:
            inner = (
                '<ul class="tree">'
                + _rows_markup(children, breakdowns, section_key, children_ancestors, depth + 1)
                + _total_line_markup(row.linked_step.get("label", ""), row.linked_step.get("unit"), row.linked_step.get("value"))
                + "</ul>"
            )
        else:
            inner = f'<p class="formula">{_text(row.linked_step.get("formula", ""))}</p>'
        if row.linked_step.get("note"):
            inner += f'<p class="note">{_text(row.linked_step["note"])}</p>'
        open_attribute = " open" if depth == 0 else ""
        parts.append(
            f'<li class="row" data-depth="{depth}"><details{open_attribute}>'
            f'<summary class="line">{_row_line_markup(row, True)}</summary>'
            f'<div class="children">{inner}</div></details></li>'
        )
    return "".join(parts)


def _result_card_markup(section: _HtmlReportResultSection, result_count: int, breakdowns: dict) -> str:
    """One result, laid out like its `CalculationBreakdownPopup`."""
    tile = section.tile
    header = (
        f'<header class="card-head"><div><p class="eyebrow">Result {section.result_index + 1} of {result_count}</p>'
        f'<h2>{_text(section.title)}</h2>'
    )
    headline_step = section.headline_step
    if headline_step is None:
        return (
            f'<section class="card" id="{section.anchor_id}">{header}</div></header>'
            '<p class="empty">No breakdown available for this result.</p></section>'
        )
    header += (
        f'<p class="headline">{_formatted(headline_step.get("unit"), headline_step.get("value"))}</p></div>'
        '<div class="card-tools" hidden>'
        '<button type="button" data-action="expand">Expand all</button>'
        '<button type="button" data-action="collapse">Collapse all</button></div></header>'
    )
    body: list[str] = []
    headline_is_sum = is_sum_step(headline_step)
    if not headline_is_sum:
        box = f'<p class="formula">{_text(headline_step.get("formula", ""))}</p>'
        if headline_step.get("note"):
            box += f'<p class="note">{_text(headline_step["note"])}</p>'
        if section.top_level_rows:
            box += '<p class="caption">Built from</p>'
        body.append(f'<div class="formula-box">{box}</div>')
    if section.top_level_rows or headline_is_sum:
        tree = _rows_markup(section.top_level_rows, breakdowns, tile.result_key, section.root_ancestor_step_labels, 0)
        if headline_is_sum:
            tree += _total_line_markup(headline_step["label"], headline_step.get("unit"), headline_step.get("value"), "total headline-total")
        body.append(f'<ul class="tree root">{tree}</ul>')
    if headline_is_sum and headline_step.get("note"):
        body.append(f'<p class="note headline-note">{_text(headline_step["note"])}</p>')
    if section.derived_rows:
        body.append('<p class="caption">Derived from this</p>')
        body.append(f'<ul class="tree root">{_rows_markup(section.derived_rows, breakdowns, tile.result_key, frozenset(), 0)}</ul>')
    all_steps = "".join(
        f'<li><div class="step-head"><span class="label">{_text(step.get("label", ""))}</span>'
        f'<span class="val">{_formatted(step.get("unit"), step.get("value"))}</span></div>'
        f'<p class="formula">{_text(step.get("formula", ""))}</p>'
        + (f'<p class="note">{_text(step["note"])}</p>' if step.get("note") else "")
        + "</li>"
        for step in section.steps
    )
    body.append(
        f'<details class="all-steps"><summary>All {len(section.steps)} steps in calculation order</summary>'
        f'<ol>{all_steps}</ol></details>'
    )
    body.append('<a class="to-top" href="#top">Back to results ↑</a>')
    return f'<section class="card" id="{section.anchor_id}">{header}{"".join(body)}</section>'


# -- the page --------------------------------------------------------------------------------------
_REPORT_SCRIPT = """
(function () {
  var root = document.documentElement;
  var tools = document.querySelectorAll('.card-tools, .page-tools');
  for (var i = 0; i < tools.length; i++) tools[i].hidden = false;
  function setAll(container, open) {
    var all = container.querySelectorAll('.tree details');
    for (var j = 0; j < all.length; j++) all[j].open = open;
  }
  document.addEventListener('click', function (event) {
    var button = event.target.closest && event.target.closest('button[data-action]');
    if (!button) return;
    var action = button.getAttribute('data-action');
    if (action === 'theme') {
      var current = root.getAttribute('data-theme') ||
        (window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark');
      root.setAttribute('data-theme', current === 'light' ? 'dark' : 'light');
      return;
    }
    setAll(button.closest('.card') || document, action === 'expand');
  });
  window.addEventListener('beforeprint', function () { setAll(document, true); });
})();
""".strip()

_REPORT_STYLE = """
:root {
  color-scheme: dark;
  --bg: #04060d; --bg-2: #0a0f1f;
  --surface: rgba(255,255,255,0.045); --surface-2: rgba(255,255,255,0.07);
  --line: rgba(148,163,255,0.14); --line-strong: rgba(148,163,255,0.30);
  --fg: #eaf0ff; --muted: #8f9bc2; --faint: #5d688f;
  --cyan: #22d3ee; --violet: #a78bfa; --blue: #60a5fa; --amber: #fbbf24;
  --glow: 0 0 24px rgba(34,211,238,0.35);
  --radius: 18px;
  --sans: ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  --mono: ui-monospace, SFMono-Regular, Menlo, Consolas, "Roboto Mono", "Liberation Mono", monospace;
}
:root[data-theme="light"] {
  color-scheme: light;
  --bg: #f4f6fc; --bg-2: #e9edf8;
  --surface: rgba(255,255,255,0.78); --surface-2: rgba(15,23,42,0.045);
  --line: rgba(30,41,90,0.12); --line-strong: rgba(30,41,90,0.26);
  --fg: #0b1430; --muted: #4b5677; --faint: #8a93b0;
  --cyan: #0891b2; --violet: #7c3aed; --blue: #2563eb; --amber: #b45309;
  --glow: none;
}
@media (prefers-color-scheme: light) {
  :root:not([data-theme="dark"]) {
    color-scheme: light;
    --bg: #f4f6fc; --bg-2: #e9edf8;
    --surface: rgba(255,255,255,0.78); --surface-2: rgba(15,23,42,0.045);
    --line: rgba(30,41,90,0.12); --line-strong: rgba(30,41,90,0.26);
    --fg: #0b1430; --muted: #4b5677; --faint: #8a93b0;
    --cyan: #0891b2; --violet: #7c3aed; --blue: #2563eb; --amber: #b45309;
    --glow: none;
  }
}
* { box-sizing: border-box; }
html { -webkit-text-size-adjust: 100%; scroll-behavior: smooth; }
body {
  margin: 0; min-height: 100vh; background: var(--bg); color: var(--fg);
  font: 15px/1.5 var(--sans); -webkit-font-smoothing: antialiased; overflow-x: hidden;
}
.aurora { position: fixed; inset: 0; z-index: 0; pointer-events: none; overflow: hidden; }
.aurora::before {
  content: ""; position: absolute; inset: -30%;
  background:
    radial-gradient(40% 35% at 20% 15%, rgba(34,211,238,0.22), transparent 70%),
    radial-gradient(35% 30% at 85% 10%, rgba(167,139,250,0.24), transparent 70%),
    radial-gradient(45% 40% at 60% 95%, rgba(96,165,250,0.16), transparent 70%);
  filter: blur(10px); animation: drift 26s ease-in-out infinite alternate;
}
.aurora::after {
  content: ""; position: absolute; inset: 0;
  background-image:
    linear-gradient(rgba(148,163,255,0.06) 1px, transparent 1px),
    linear-gradient(90deg, rgba(148,163,255,0.06) 1px, transparent 1px);
  background-size: 44px 44px;
  -webkit-mask-image: radial-gradient(ellipse at 50% 0%, #000 0%, transparent 70%);
  mask-image: radial-gradient(ellipse at 50% 0%, #000 0%, transparent 70%);
}
:root[data-theme="light"] .aurora::before { opacity: 0.55; }
@keyframes drift { from { transform: translate3d(-3%, -2%, 0) rotate(0deg); } to { transform: translate3d(3%, 2%, 0) rotate(6deg); } }
.page { position: relative; z-index: 1; max-width: 920px; margin: 0 auto; padding: 28px 16px 48px; }
.hero { padding: 8px 0 22px; }
.brand { display: flex; align-items: center; gap: 12px; }
.brand svg { width: 40px; height: 40px; flex: none; filter: drop-shadow(0 0 12px rgba(34,211,238,0.45)); }
.brand-name { font-weight: 800; letter-spacing: 0.32em; font-size: 12px; color: var(--muted); }
.brand-sub { font-size: 12px; color: var(--faint); letter-spacing: 0.04em; }
.title-row { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; margin-top: 22px; }
h1 {
  margin: 0; font-size: clamp(26px, 6vw, 40px); line-height: 1.1; letter-spacing: -0.02em; font-weight: 800;
  background: linear-gradient(92deg, var(--fg) 30%, var(--cyan) 70%, var(--violet));
  -webkit-background-clip: text; background-clip: text; color: transparent; overflow-wrap: anywhere;
}
.badge {
  flex: none; font: 700 11px/1 var(--sans); letter-spacing: 0.18em; padding: 8px 12px; border-radius: 999px;
  color: var(--cyan); border: 1px solid var(--cyan); background: rgba(34,211,238,0.08); box-shadow: var(--glow);
}
.badge.flip { color: var(--amber); border-color: var(--amber); background: rgba(251,191,36,0.08); box-shadow: 0 0 24px rgba(251,191,36,0.25); }
.meta { margin: 10px 0 0; color: var(--muted); font-size: 13px; }
.hint { margin: 14px 0 0; display: inline-flex; align-items: center; gap: 8px; font-size: 13px; color: var(--muted);
  padding: 8px 12px; border: 1px dashed var(--line-strong); border-radius: 12px; background: var(--surface); }
.hint .chev { display: inline-block; flex: none; }
.tiles { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 10px; margin: 22px 0 8px; }
.tile {
  display: block; text-decoration: none; color: inherit; padding: 14px 14px 12px; border-radius: 14px;
  background: linear-gradient(160deg, var(--surface-2), var(--surface)); border: 1px solid var(--line);
  transition: transform .2s ease, border-color .2s ease, box-shadow .2s ease; position: relative; overflow: hidden;
}
.tile::after { content: ""; position: absolute; inset: 0 0 auto 0; height: 2px; background: linear-gradient(90deg, var(--cyan), var(--violet)); opacity: .7; }
.tile:hover, .tile:focus-visible { transform: translateY(-2px); border-color: var(--line-strong); box-shadow: var(--glow); outline: none; }
.tile-label { display: block; font-size: 12px; color: var(--muted); }
.tile-value { display: block; margin-top: 4px; font: 700 19px/1.2 var(--mono); font-variant-numeric: tabular-nums; letter-spacing: -0.01em; overflow-wrap: anywhere; }
.page-tools { display: flex; justify-content: flex-end; gap: 8px; margin: 8px 0 0; }
button {
  font: 600 12px/1 var(--sans); color: var(--fg); background: var(--surface-2); border: 1px solid var(--line);
  border-radius: 999px; padding: 9px 14px; cursor: pointer; min-height: 34px;
}
button:hover { border-color: var(--cyan); color: var(--cyan); }
.card {
  margin: 18px 0; padding: 20px 18px; border-radius: var(--radius); background: var(--surface);
  border: 1px solid var(--line); backdrop-filter: blur(14px); -webkit-backdrop-filter: blur(14px);
  box-shadow: 0 20px 60px -30px rgba(0,0,0,0.6); scroll-margin-top: 16px;
}
.card-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; flex-wrap: wrap; }
.eyebrow { margin: 0; font: 700 10px/1 var(--sans); letter-spacing: 0.22em; text-transform: uppercase; color: var(--cyan); }
h2 { margin: 8px 0 0; font-size: 17px; font-weight: 650; letter-spacing: -0.01em; }
.headline {
  margin: 6px 0 0; font: 800 clamp(26px, 7vw, 34px)/1.1 var(--mono); font-variant-numeric: tabular-nums; letter-spacing: -0.02em;
  text-shadow: 0 0 28px rgba(34,211,238,0.35); overflow-wrap: anywhere;
}
:root[data-theme="light"] .headline { text-shadow: none; }
.card-tools { display: flex; gap: 6px; flex-wrap: wrap; }
.card-tools[hidden], .page-tools[hidden] { display: none; }
.formula-box { margin: 16px 0 12px; padding: 12px 14px; border-radius: 14px; border: 1px solid rgba(34,211,238,0.35); background: rgba(34,211,238,0.06); }
.formula { margin: 0; font: 12.5px/1.6 var(--mono); color: var(--fg); overflow-wrap: anywhere; }
.note { margin: 6px 0 0; font-size: 12.5px; color: var(--muted); }
.headline-note { margin-top: 8px; }
.caption { margin: 14px 0 6px; font: 700 10.5px/1 var(--sans); letter-spacing: 0.18em; text-transform: uppercase; color: var(--muted); }
.formula-box .caption { margin-bottom: 0; }
.tree { list-style: none; margin: 0; padding: 0; }
.tree.root { margin-top: 14px; padding: 4px 12px; border-radius: 14px; background: var(--surface-2); border: 1px solid var(--line); }
.line, .total {
  display: grid; grid-template-columns: 18px 14px minmax(0,1fr) auto; align-items: baseline; column-gap: 8px;
  padding: 7px 0; font-size: 14px;
}
summary.line { cursor: pointer; list-style: none; border-radius: 8px; -webkit-tap-highlight-color: transparent; }
summary.line::-webkit-details-marker { display: none; }
summary.line:hover .label { color: var(--cyan); }
summary.line:focus-visible { outline: 2px solid var(--cyan); outline-offset: 2px; }
.chev, .chev-space { width: 18px; height: 18px; align-self: center; }
.chev { position: relative; border-radius: 6px; background: var(--surface-2); border: 1px solid var(--line); }
.chev::before {
  content: ""; position: absolute; left: 6px; top: 5px; width: 5px; height: 5px;
  border-right: 1.6px solid var(--cyan); border-bottom: 1.6px solid var(--cyan);
  transform: rotate(-45deg); transition: transform .2s ease;
}
details[open] > summary .chev::before { transform: rotate(45deg); left: 5px; top: 4px; }
.sign { text-align: center; font-family: var(--mono); color: var(--faint); }
.label { min-width: 0; overflow-wrap: anywhere; }
.row.leaf .label { color: var(--muted); }
.row:not(.leaf) > details > summary .label { font-weight: 600; }
.val { font-family: var(--mono); font-variant-numeric: tabular-nums; text-align: right; white-space: nowrap; }
.children { margin: 0 0 6px 8px; padding: 2px 0 4px 14px; border-left: 1px solid var(--line-strong); position: relative; }
.children::before { content: ""; position: absolute; left: -1px; top: 0; width: 1px; height: 28px; background: linear-gradient(var(--cyan), transparent); }
.children > .formula { padding: 6px 0 2px; font-size: 12px; }
.total { border-top: 1px solid var(--line); font-weight: 650; }
.headline-total { border-top: 2px solid rgba(34,211,238,0.55); font-weight: 800; font-size: 15px; }
.headline-total .val { color: var(--cyan); }
.all-steps { margin-top: 16px; }
.all-steps > summary {
  cursor: pointer; font: 700 10.5px/1 var(--sans); letter-spacing: 0.18em; text-transform: uppercase; color: var(--muted);
  padding: 8px 0; list-style: none;
}
.all-steps > summary::-webkit-details-marker { display: none; }
.all-steps > summary::before { content: "+ "; color: var(--cyan); }
.all-steps[open] > summary::before { content: "− "; }
.all-steps ol { margin: 8px 0 0; padding: 0; list-style: none; counter-reset: step; display: grid; gap: 8px; }
.all-steps li { padding: 10px 12px; border-radius: 12px; background: var(--surface-2); border: 1px solid var(--line); counter-increment: step; }
.step-head { display: flex; justify-content: space-between; gap: 12px; font-weight: 650; font-size: 13.5px; }
.step-head .label::before { content: counter(step) ". "; color: var(--faint); font-family: var(--mono); }
.all-steps .formula { margin-top: 4px; font-size: 12px; }
.to-top { display: inline-block; margin-top: 12px; font-size: 12px; color: var(--cyan); text-decoration: none; }
.empty { color: var(--muted); }
.legend { margin: 26px 0 0; color: var(--muted); font-size: 12px; }
footer { margin-top: 26px; padding-top: 18px; border-top: 1px solid var(--line); color: var(--faint); font-size: 11.5px; }
footer strong { color: var(--fg); letter-spacing: 0.04em; }
@media (max-width: 520px) {
  .page { padding: 18px 12px 40px; }
  .card { padding: 16px 12px; border-radius: 16px; }
  .tree.root { padding: 2px 8px; }
  .line, .total { grid-template-columns: 18px 12px minmax(0,1fr) auto; column-gap: 6px; font-size: 13.5px; }
  .children { margin-left: 6px; padding-left: 10px; }
  .tiles { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .title-row { flex-direction: column-reverse; }
}
@media (prefers-reduced-motion: reduce) {
  html { scroll-behavior: auto; }
  .aurora::before { animation: none; }
  .tile, .chev::before { transition: none; }
}
@media print {
  :root { color-scheme: light; --bg: #fff; --surface: #fff; --surface-2: #f6f7fb; --line: #dfe3ee; --line-strong: #c9cfe0;
    --fg: #0b1430; --muted: #4b5677; --faint: #8a93b0; --cyan: #0e7490; --glow: none; }
  .aurora, .page-tools, .card-tools, .to-top, .hint { display: none !important; }
  .card { break-inside: avoid-page; box-shadow: none; backdrop-filter: none; }
  h1 { color: var(--fg); background: none; }
  .headline { text-shadow: none; }
}
""".strip()

_BRAND_MARK_SVG = (
    '<svg viewBox="0 0 48 48" aria-hidden="true"><defs><linearGradient id="bw-g" x1="0" y1="0" x2="1" y2="1">'
    '<stop offset="0" stop-color="#22d3ee"/><stop offset="1" stop-color="#a78bfa"/></linearGradient></defs>'
    '<circle cx="24" cy="24" r="22" fill="none" stroke="url(#bw-g)" stroke-width="2"/>'
    '<path d="M9 27c5 0 8-3 11-7 2 5 6 8 12 8 3 0 5-1 7-3-1 6-7 11-15 11-8 0-14-4-15-9z" fill="url(#bw-g)"/>'
    '<path d="M33 15c1-3 4-5 7-5-1 2-1 4 0 6-2 0-4 0-5 1z" fill="url(#bw-g)"/></svg>'
)


def _csp_hash(source: str) -> str:
    return "sha256-" + base64.b64encode(hashlib.sha256(source.encode("utf-8")).digest()).decode("ascii")


REPORT_CONTENT_SECURITY_POLICY = (
    "default-src 'none'; style-src 'unsafe-inline'; img-src data:; "
    f"script-src '{_csp_hash(_REPORT_SCRIPT)}'; base-uri 'none'; form-action 'none'"
)


def build_deal_html_report(
    address: str,
    deal_type: str,
    result: dict,
    selected_result_keys: list[str] | None = None,
) -> str:
    """Render the interactive deal report as one self-contained HTML document.

    `result` is the calculator output as a dict, carrying `breakdowns`. `selected_result_keys` picks the
    result tiles (None = every tile); `select_report_result_tiles` rejects unknown keys and an empty list.
    """
    deal_type = (deal_type or "BRRRR").upper()
    breakdowns = result.get("breakdowns") or {}
    tiles = select_report_result_tiles(deal_type, selected_result_keys)
    sections = [_build_html_report_result_section(index, tile, result, breakdowns) for index, tile in enumerate(tiles)]
    address_text = _text(address or "Property")
    generated_on = datetime.now().strftime("%b %d, %Y")

    result_tiles = "".join(
        f'<a class="tile" href="#{section.anchor_id}"><span class="tile-label">{_text(section.tile.tile_label)}</span>'
        f'<span class="tile-value">{_formatted(section.tile.unit, result.get(section.tile.result_key))}</span></a>'
        for section in sections
    )
    cards = "".join(_result_card_markup(section, len(sections), breakdowns) for section in sections)
    badge_class = "badge flip" if deal_type == "FLIP" else "badge"
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta http-equiv="Content-Security-Policy" content="{REPORT_CONTENT_SECURITY_POLICY}">
<meta name="color-scheme" content="dark light">
<meta name="theme-color" content="#04060d">
<meta name="robots" content="noindex">
<title>{address_text} · {deal_type} Deal Report · Big Whales</title>
<style>{_REPORT_STYLE}</style>
</head>
<body>
<div class="aurora" aria-hidden="true"></div>
<div class="page" id="top">
<header class="hero">
<div class="brand">{_BRAND_MARK_SVG}<div><div class="brand-name">BIG WHALES</div><div class="brand-sub">Real-estate analytics</div></div></div>
<div class="title-row"><h1>{address_text}</h1><span class="{badge_class}">{deal_type}</span></div>
<p class="meta">Interactive Deal Report · Generated {generated_on}</p>
<p class="hint"><span class="chev" aria-hidden="true"></span>Tap any row with this arrow to see how it is calculated.</p>
<nav class="tiles" aria-label="Results">{result_tiles}</nav>
<div class="page-tools" hidden>
<button type="button" data-action="expand">Expand everything</button>
<button type="button" data-action="collapse">Collapse everything</button>
<button type="button" data-action="theme">Light / Dark</button>
</div>
</header>
<main>{cards}</main>
<p class="legend">Money is in dollars, percentages as shown, ratios as a multiple (1.20x). "∞" and "-∞" mean the divisor was zero. A note under a step explains a convention.</p>
<footer>
<p><strong>Big Whales AY LLC</strong> · Real-estate analytics by big whales · BigWhalesLLC@gmail.com</p>
<p>Disclaimer: This report is generated for informational purposes only and does not constitute financial, tax, or legal advice. Verify all figures with a licensed professional before transacting.</p>
</footer>
</div>
<script>{_REPORT_SCRIPT}</script>
</body>
</html>
"""
