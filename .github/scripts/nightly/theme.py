"""The site's "Quiet Luxury" look, as inline-CSS building blocks for the email.

Values come from ``frontend/scripts/design/looks.data.mjs`` (luxury, light
mode). Rules borrowed from the design system: routine items are ink on hairlines;
status is a 10 % wash pill with tinted text, never a filled block; a KPI number
is never colour-coded, its delta line carries sign, word and colour; strong
colour is reserved for genuine anomalies.
"""

from __future__ import annotations

import html

PAGE = "#f7f4ee"
CARD = "#ffffff"
PANEL = "#f1ede4"
TIER3 = "#e8e2d6"
LINE = "#dcd6ca"
INK = "#1d1c1a"
MUTED = "#524e46"
ACCENT = "#7d5f27"
ACCENT2 = "#3f5a7a"
POSITIVE = "#2f6f3a"
NEGATIVE = "#a33a3a"
WARNING = "#7f5311"

# 10 % washes of the status colours on white, precomputed for mail clients.
WASH = {
    "positive": "#eaf1eb",
    "negative": "#f6ebeb",
    "warning": "#f2ece2",
    "accent": "#f2efe9",
    "accent2": "#eceff2",
    "neutral": PANEL,
}
TONE_COLOUR = {
    "positive": POSITIVE, "negative": NEGATIVE, "warning": WARNING,
    "accent": ACCENT, "accent2": ACCENT2, "neutral": MUTED,
}

# Chart series, fixed order (never cycled).
CHART_SERIES = ["#7d5f27", "#2f6f3a", "#7f5311", "#3f5a7a", "#a33a3a", "#6b4fa0", "#a05a2c", "#2f6f6a"]
DEEMPHASIS = "#bab5aa"

# Short stacks on purpose: they repeat hundreds of times in the inline CSS and
# Gmail clips mail over ~102 KB. The tails are the site's own token fallbacks.
DISPLAY = "Fraunces,Georgia,serif"
BODY = "Inter,system-ui,sans-serif"
MONO = "'JetBrains Mono',Menlo,monospace"

RADIUS_CARD = "12px"
SHADOW_1 = "0 1px 2px 0 rgba(29,28,26,.06)"

e = html.escape


def outcome_tone(outcome: str) -> str:
    return {"success": "positive", "failure": "negative", "cancelled": "warning"}.get(outcome, "neutral")


def severity_tone(severity: str) -> str:
    return {"critical": "negative", "warning": "warning", "notice": "accent2"}.get(severity, "neutral")


def pill(text: str, tone: str = "neutral") -> str:
    return (
        f'<span style="display:inline-block;padding:2px 9px;border-radius:9999px;background:{WASH[tone]};'
        f'color:{TONE_COLOUR[tone]};font:500 12px/18px {BODY};white-space:nowrap;">{e(text)}</span>'
    )


def eyebrow(text: str, colour: str = ACCENT) -> str:
    return (
        f'<div style="font-family:{MONO};font-size:11px;font-weight:600;letter-spacing:.14em;'
        f'text-transform:uppercase;color:{colour};">{e(text)}</div>'
    )


def label(text: str) -> str:
    return (
        f'<div style="font-family:{BODY};font-size:11px;font-weight:600;letter-spacing:.10em;'
        f'text-transform:uppercase;color:{MUTED};">{e(text)}</div>'
    )


def display(text: str, size: int = 24, weight: int = 600) -> str:
    return (
        f'<div style="font-family:{DISPLAY};font-size:{size}px;font-weight:{weight};letter-spacing:-0.015em;'
        f'color:{INK};line-height:1.15;">{text}</div>'
    )


def body_text(text: str, size: int = 14, colour: str = INK) -> str:
    return f'<div style="font-family:{BODY};font-size:{size}px;color:{colour};line-height:1.5;">{text}</div>'


def mono(text: str, size: int = 13, colour: str = INK, weight: int = 400) -> str:
    return (
        f'<span style="font:{weight} {size}px {MONO};color:{colour};">{text}</span>'
    )


def tile(label_text: str, value, delta_lines: list[tuple[str, str]]) -> str:
    """A KPI tile: label, ink value (never coloured), then delta lines as (text, tone)."""
    deltas = "".join(
        f'<div style="font-family:{BODY};font-size:12px;color:{TONE_COLOUR[tone]};margin-top:4px;">{e(text)}</div>'
        for text, tone in delta_lines
    ) or f'<div style="font-family:{BODY};font-size:12px;color:{MUTED};margin-top:4px;">&nbsp;</div>'
    return (
        f'<td width="25%" style="padding:0 6px;vertical-align:top;">'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        f'style="background:{CARD};border:1px solid {LINE};border-radius:{RADIUS_CARD};">'
        f'<tr><td style="padding:14px 14px 12px 14px;">'
        f'{label(label_text)}'
        f'<div style="font-family:{DISPLAY};font-size:28px;font-weight:600;letter-spacing:-0.015em;color:{INK};'
        f'line-height:1.1;margin-top:8px;font-variant-numeric:tabular-nums;">{value}</div>'
        f'{deltas}'
        f'</td></tr></table></td>'
    )


def section(title: str, inner: str, marker: str = "") -> str:
    """A section with an eyebrow title over a hairline. ``marker`` is an optional pill HTML."""
    head = (
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>'
        f'<td style="padding-bottom:10px;border-bottom:1px solid {LINE};">{eyebrow(title, MUTED)}</td>'
        f'<td align="right" style="padding-bottom:10px;border-bottom:1px solid {LINE};">{marker}</td>'
        f'</tr></table>'
    )
    return (
        f'<tr><td style="padding:22px 32px 4px 32px;">{head}'
        f'<div style="padding-top:12px;">{inner}</div></td></tr>'
    )


def row(left: str, right: str = "", *, last: bool = False) -> str:
    border = "" if last else f"border-bottom:1px solid {LINE};"
    return (
        f'<tr><td style="padding:9px 0;{border}font:14px {BODY};color:{INK};">{left}</td>'
        f'<td align="right" style="padding:9px 0 9px 16px;{border}white-space:nowrap;">{right}</td></tr>'
    )


def table(rows_html: str) -> str:
    return f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0">{rows_html}</table>'


def th(text: str, align: str = "left") -> str:
    return (
        f'<th align="{align}" style="padding:6px 6px;font-family:{BODY};font-size:11px;font-weight:600;'
        f'letter-spacing:.08em;text-transform:uppercase;color:{MUTED};border-bottom:1px solid {LINE};">{e(text)}</th>'
    )


def td(inner: str, align: str = "left", extra: str = "") -> str:
    return f'<td align="{align}" style="padding:8px 6px;border-bottom:1px solid {LINE};{extra}">{inner}</td>'


def bar(pct: int, tone: str = "accent", width: int = 130) -> str:
    """A single-hue magnitude bar (renders in every major mail client)."""
    pct = max(2, min(100, int(pct)))
    return (
        f'<div style="width:{width}px;height:6px;background:{PANEL};border-radius:3px;">'
        f'<div style="width:{pct}%;height:6px;background:{TONE_COLOUR[tone]};border-radius:3px;"></div></div>'
    )


def note(text: str) -> str:
    return f'<div style="font-family:{BODY};font-size:13px;color:{MUTED};line-height:1.5;">{text}</div>'
