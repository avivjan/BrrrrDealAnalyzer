/**
 * Colour lookup for the liquidity timeline `<canvas>`.
 *
 * Every other colour in the app is a Tailwind class backed by a CSS custom
 * property, but a canvas takes a resolved string — `ctx.fillStyle = 'red-500'`
 * is silently ignored, not an error. So the chart's palette lives in
 * `tokens.css` as `--chart-*` literals and is read out through here.
 *
 * Two properties matter to the caller:
 *
 * - **It never throws.** A bad or missing custom property returns the literal
 *   the chart used before the tokens existed, so the worst case is that the
 *   chart looks exactly like it did in Phase 0 rather than disappearing.
 * - **It reads the stylesheet once per name.** `draw()` runs on every hover,
 *   pan and resize and asks for dozens of colours each time; `getComputedStyle`
 *   forces a style recalculation, so calling it in that loop would be a
 *   per-frame cost for values that cannot change between frames.
 *
 * `resetChartTokenCache()` exists for tests and for a future theme switch,
 * which will need to invalidate the cache before redrawing.
 */

/** Every `--chart-*` token, without the prefix. */
export type ChartTokenName =
  | "bg"
  | "grid"
  | "axis-text"
  | "reserve-band"
  | "weekend-band"
  | "today-band"
  | "month-line"
  | "day-line"
  | "month-label"
  | "day-today"
  | "day-hover"
  | "day-active"
  | "day-idle"
  | "marker-today"
  | "marker-idle"
  | "today-line"
  | "net-positive"
  | "net-negative"
  | "inflow-fill-hover"
  | "inflow-fill"
  | "inflow-stroke-hover"
  | "inflow-stroke"
  | "outflow-fill-hover"
  | "outflow-fill"
  | "outflow-stroke-hover"
  | "outflow-stroke"
  | "reserve-line"
  | "baseline"
  | "balance-dot"
  | "balance-dot-core"
  | "min-negative"
  | "min-warning";

/**
 * The literals `TimelineChart.vue` assigns today, character for character.
 *
 * They are duplicated from `tokens.css` on purpose: the chart must keep
 * drawing if the stylesheet has not applied yet (or at all, as in a unit test
 * or an SSR pass), and a test in this directory holds the two copies together.
 */
export const CHART_FALLBACKS: Record<ChartTokenName, string> = {
  bg: "#0f1117",
  grid: "#1e2030",
  "axis-text": "#5c6078",
  "reserve-band": "rgba(239, 68, 68, 0.04)",
  "weekend-band": "rgba(255,255,255,0.015)",
  "today-band": "rgba(99, 102, 241, 0.08)",
  "month-line": "#2a2f45",
  "day-line": "#16192a",
  "month-label": "#7c82a0",
  "day-today": "#818cf8",
  "day-hover": "#c7d2fe",
  "day-active": "#94a3b8",
  "day-idle": "#3e4460",
  "marker-today": "#6366f1",
  "marker-idle": "#2e3350",
  "today-line": "#6366f1",
  "net-positive": "#22c55e",
  "net-negative": "#ef4444",
  "inflow-fill-hover": "rgba(129, 140, 248, 0.55)",
  "inflow-fill": "rgba(99, 102, 241, 0.35)",
  "inflow-stroke-hover": "#a5b4fc",
  "inflow-stroke": "#818cf8",
  "outflow-fill-hover": "rgba(239, 68, 68, 0.55)",
  "outflow-fill": "rgba(239, 68, 68, 0.35)",
  "outflow-stroke-hover": "#fca5a5",
  "outflow-stroke": "#ef4444",
  "reserve-line": "#ef4444",
  baseline: "rgba(148, 163, 184, 0.2)",
  "balance-dot": "#818cf8",
  "balance-dot-core": "#fff",
  "min-negative": "#ef4444",
  "min-warning": "#f59e0b",
};

/** Resolved values, keyed by token name. Only populated when a DOM exists. */
const resolved = new Map<ChartTokenName, string>();

/** Drop the memoised values, so the next `chartToken` re-reads the stylesheet. */
export function resetChartTokenCache(): void {
  resolved.clear();
}

/** Read `--chart-<name>` off the root element, or `''` if that is not possible. */
function readCustomProperty(name: ChartTokenName): string {
  try {
    return getComputedStyle(document.documentElement)
      .getPropertyValue(`--chart-${name}`)
      .trim();
  } catch {
    // A detached or half-built document, or a host without getComputedStyle.
    return "";
  }
}

/**
 * The colour string for one chart token: the stylesheet's value if there is
 * one, otherwise the literal the chart shipped with.
 */
export function chartToken(name: ChartTokenName): string {
  const cached = resolved.get(name);
  if (cached !== undefined) return cached;

  const fallback = CHART_FALLBACKS[name] ?? "";
  // Nothing to read and nothing to cache: without a document the answer is the
  // fallback, and caching it would freeze the chart on fallbacks for the rest
  // of the page if a DOM appeared later.
  if (typeof document === "undefined") return fallback;

  const value = readCustomProperty(name) || fallback;
  resolved.set(name, value);
  return value;
}
