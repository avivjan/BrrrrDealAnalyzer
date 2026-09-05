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
 * `resetChartTokenCache()` is called by `src/design/theme.ts` on every look or
 * mode switch, before the chart's colour `computed` re-evaluates.
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
 * The default look's dark chart palette (`src/assets/looks/luxury.css`,
 * `[data-look="luxury"].dark`), character for character.
 *
 * Duplicated on purpose: the chart must keep drawing if the stylesheet has not
 * applied yet (or at all, as in a unit test or an SSR pass), and
 * `chartTokens.test.ts` holds this copy to the generated sheet. When the
 * default look changes, regenerate this table from `chartLiterals()` in
 * `scripts/design/build-looks.mjs`.
 */
export const CHART_FALLBACKS: Record<ChartTokenName, string> = {
  bg: "#1b1d24",
  grid: "#2f323d",
  "axis-text": "#a8a49b",
  "reserve-band": "rgba(224, 149, 149, 0.06)",
  "weekend-band": "rgba(236, 231, 221, 0.04)",
  "today-band": "rgba(212, 180, 131, 0.08)",
  "month-line": "#51535a",
  "day-line": "#2f323d",
  "month-label": "#a8a49b",
  "day-today": "#d4b483",
  "day-hover": "#e2c99c",
  "day-active": "#ece7dd",
  "day-idle": "rgba(168, 164, 155, 0.7)",
  "marker-today": "#d4b483",
  "marker-idle": "rgba(168, 164, 155, 0.65)",
  "today-line": "#d4b483",
  "net-positive": "#8fbf8a",
  "net-negative": "#e09595",
  "inflow-fill-hover": "rgba(212, 180, 131, 0.55)",
  "inflow-fill": "rgba(212, 180, 131, 0.35)",
  "inflow-stroke-hover": "#e2c99c",
  "inflow-stroke": "#d4b483",
  "outflow-fill-hover": "rgba(224, 149, 149, 0.55)",
  "outflow-fill": "rgba(224, 149, 149, 0.35)",
  "outflow-stroke-hover": "#e2a5a3",
  "outflow-stroke": "#e09595",
  "reserve-line": "#e09595",
  baseline: "rgba(168, 164, 155, 0.2)",
  "balance-dot": "#d4b483",
  "balance-dot-core": "#1b1d24",
  "min-negative": "#e09595",
  "min-warning": "#e0b96a",
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

  // With a document, whatever comes back is cached for the page -- including
  // the fallback, when the property resolves empty. That is deliberate: the
  // stylesheet either has the token or it never will, and re-asking on every
  // frame would force a style recalculation to learn the same nothing. It is
  // also harmless in Phase 1, where each fallback *is* the token's value.
  // A future theme switch changes that, and must call resetChartTokenCache()
  // before it redraws.
  const value = readCustomProperty(name) || fallback;
  resolved.set(name, value);
  return value;
}
