"""Static trend charts as PNG bytes (matplotlib, Agg), with a table fallback.

Design rules applied: one axis per chart; 2 px lines; ≥8 px markers with a
surface ring; a legend whenever two or more series are drawn; text in ink/muted
tokens, never in a series colour; emphasis (accent + gray) when one series is the
story; the site's chart palette in fixed order for categories.
"""

from __future__ import annotations

import datetime as dt
import io

from . import theme

WIDTH_PX, HEIGHT_PX, DPI = 1280, 440, 200  # renders at 640×220 CSS px

# Site palette in its fixed order, minus the two colours that clash here: warning bronze
# (#7f5311) is indistinguishable from accent bronze at 2 px, and negative red is
# reserved for the "Unknown / un-annotated" series.
CATEGORY_SERIES = [c for c in theme.CHART_SERIES if c not in (theme.WARNING, theme.NEGATIVE)]


def available() -> bool:
    try:
        import matplotlib  # noqa: F401
        matplotlib.use("Agg")
        import matplotlib.pyplot  # noqa: F401
        return True
    except Exception:
        return False


def _run_labels(records: list[dict]) -> list[str]:
    labels = []
    for r in records:
        started = (r.get("run") or {}).get("started") or ""
        try:
            labels.append(dt.datetime.fromisoformat(started.replace("Z", "+00:00")).strftime("%d %b"))
        except ValueError:
            labels.append(str((r.get("run") or {}).get("number") or "?"))
    return labels


def _xticks(ax, x: list[int], labels: list[str], max_labels: int = 8) -> None:
    """Show every run as a tick but label at most ``max_labels`` of them, evenly spaced, so dates never collide."""
    ax.set_xticks(x)
    n = len(x)
    if n <= max_labels:
        ax.set_xticklabels(labels)
        return
    keep = {round(i * (n - 1) / (max_labels - 1)) for i in range(max_labels)}
    ax.set_xticklabels([lab if i in keep else "" for i, lab in enumerate(labels)])


def _style(ax, title: str):
    import matplotlib.pyplot as plt  # noqa: F401
    ax.set_facecolor(theme.CARD)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    for spine in ("left", "bottom"):
        ax.spines[spine].set_color(theme.LINE)
    ax.tick_params(colors=theme.MUTED, labelsize=8, length=0)
    ax.grid(axis="y", color=theme.LINE, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.set_title(title, loc="left", fontsize=10, color=theme.INK, pad=10)


def _finish(fig) -> bytes:
    import matplotlib.pyplot as plt
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=DPI, facecolor=theme.CARD, bbox_inches="tight", pad_inches=0.15)
    plt.close(fig)
    return buf.getvalue()


def _legend(ax, ncol: int = 4):
    return ax.legend(loc="upper left", frameon=False, fontsize=8, ncol=ncol, bbox_to_anchor=(0, -0.14),
                     labelcolor=theme.MUTED)


def pass_fail_over_time(records: list[dict]) -> bytes:
    import matplotlib.pyplot as plt
    x = list(range(len(records)))
    labels = _run_labels(records)
    stats = [((r.get("playwright") or {}).get("stats") or {}) for r in records]
    fig, ax = plt.subplots(figsize=(WIDTH_PX / DPI, HEIGHT_PX / DPI), dpi=DPI)
    _style(ax, "Playwright results per nightly run")
    series = (
        ("passed", [s.get("expected", 0) for s in stats], theme.ACCENT),
        ("failed", [s.get("unexpected", 0) for s in stats], theme.NEGATIVE),
        ("skipped", [s.get("skipped", 0) for s in stats], theme.DEEMPHASIS),
    )
    for name, ys, colour in series:
        ax.plot(x, ys, color=colour, linewidth=2, solid_joinstyle="round", solid_capstyle="round", label=name)
        ax.scatter(x, ys, s=22, color=colour, edgecolors=theme.CARD, linewidths=1.2, zorder=3)
        ax.annotate(f"{ys[-1]:g}", (x[-1], ys[-1]), textcoords="offset points", xytext=(6, 0),
                    fontsize=8, color=theme.INK, va="center")
    _xticks(ax, x, labels)
    ax.set_ylim(bottom=0)
    _legend(ax)
    return _finish(fig)


def skips_by_category(records: list[dict], allowlist: dict) -> bytes:
    import matplotlib.pyplot as plt
    categories: list[str] = []
    cat_of: dict[str, str] = {}
    for entry in allowlist.get("reasons", []):
        cat = entry.get("category", "Other")
        cat_of[entry["id"]] = cat
        if cat not in categories:
            categories.append(cat)
    categories.append("Unknown / un-annotated")
    x = list(range(len(records)))
    labels = _run_labels(records)
    fig, ax = plt.subplots(figsize=(WIDTH_PX / DPI, HEIGHT_PX / DPI), dpi=DPI)
    _style(ax, "Skipped tests per run, by allow-list category")
    drawn = 0
    for i, cat in enumerate(categories):
        ys = []
        for r in records:
            skips = ((r.get("playwright") or {}).get("skips") or {})
            total = 0
            for gid, by_project in skips.items():
                gcat = cat_of.get(gid, "Unknown / un-annotated")
                if gcat == cat:
                    total += sum(by_project.values())
            ys.append(total)
        if not any(ys):
            continue
        colour = theme.NEGATIVE if cat == "Unknown / un-annotated" else CATEGORY_SERIES[i % len(CATEGORY_SERIES)]
        ax.plot(x, ys, color=colour, linewidth=2, label=cat, solid_joinstyle="round")
        ax.scatter(x, ys, s=18, color=colour, edgecolors=theme.CARD, linewidths=1.2, zorder=3)
        drawn += 1
    _xticks(ax, x, labels)
    ax.set_ylim(bottom=0)
    if drawn >= 2:
        _legend(ax, ncol=2)  # category names are long; two columns keep the legend within the axes' width
    return _finish(fig)


def slowest_trend(records: list[dict], keys: list[str]) -> bytes:
    """Tonight's five slowest tests over the recorded runs; tonight's #1 in accent, the rest de-emphasised."""
    import matplotlib.pyplot as plt
    x = list(range(len(records)))
    labels = _run_labels(records)
    fig, ax = plt.subplots(figsize=(WIDTH_PX / DPI, HEIGHT_PX / DPI), dpi=DPI)
    _style(ax, "Tonight's slowest tests, seconds per run")
    grays = ["#9a958b", "#aeaaa0", "#bab5aa", "#c8c3b8"]
    for i, key in enumerate(keys[:5]):
        ys = [((r.get("playwright") or {}).get("durations") or {}).get(key) for r in records]
        ys = [None if v is None else v / 1000 for v in ys]
        colour = theme.ACCENT if i == 0 else grays[(i - 1) % len(grays)]
        short = key.split(" :: ")[-1]
        short = short if len(short) <= 42 else short[:39] + "…"
        ax.plot(x, ys, color=colour, linewidth=2 if i == 0 else 1.6, label=f"[{key.split(' :: ')[0]}] {short}",
                solid_joinstyle="round")
        pts = [(xi, yi) for xi, yi in zip(x, ys) if yi is not None]
        if pts:
            ax.scatter([p[0] for p in pts], [p[1] for p in pts], s=18, color=colour,
                       edgecolors=theme.CARD, linewidths=1.2, zorder=3)
    _xticks(ax, x, labels)
    ax.set_ylim(bottom=0)
    if len(keys) >= 2:
        leg = ax.legend(loc="upper left", frameon=False, fontsize=7, ncol=1, bbox_to_anchor=(0, -0.14),
                        labelcolor=theme.MUTED)
    return _finish(fig)


def render_all(records: list[dict], allowlist: dict, slow_keys: list[str]) -> dict[str, bytes]:
    """Return {chart_name: png_bytes}; empty when charts cannot be drawn."""
    if len(records) < 2 or not available():
        return {}
    out = {"pass_fail": pass_fail_over_time(records), "skips": skips_by_category(records, allowlist)}
    if slow_keys:
        out["slowest"] = slowest_trend(records, slow_keys)
    return out


def fallback_rows(records: list[dict], limit: int = 14) -> list[dict]:
    """Plain rows for the last runs when no image can be drawn."""
    rows = []
    for r, lab in zip(records[-limit:], _run_labels(records[-limit:])):
        s = (r.get("playwright") or {}).get("stats") or {}
        number = (r.get("run") or {}).get("number")
        rows.append({
            "label": lab, "number": number if number is not None else "tonight",
            "passed": s.get("expected", 0), "failed": s.get("unexpected", 0), "skipped": s.get("skipped", 0),
            "minutes": (s.get("duration_ms", 0) or 0) / 60000,
            "verdict": r.get("verdict", "?"),
        })
    return rows
