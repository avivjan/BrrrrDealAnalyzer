import { readFileSync } from "node:fs";
import { afterEach, describe, expect, it } from "vitest";

import {
  CHART_FALLBACKS,
  chartToken,
  resetChartTokenCache,
  type ChartTokenName,
} from "./chartTokens";

const NAMES = Object.keys(CHART_FALLBACKS) as ChartTokenName[];

const read = (relative: string) =>
  readFileSync(new URL(relative, import.meta.url), "utf8");

/**
 * The colours `TimelineChart.vue` used to assign directly, character for
 * character.
 *
 * They lived in the component until Task 3.9 replaced each one with a
 * `chartToken('<name>')` call (gate G3's E1 exemption), so the component can
 * no longer be the second copy this file holds `CHART_FALLBACKS` against. The
 * table moves here instead: it is the dark theme's palette, and the two
 * assertions below tie it to both `CHART_FALLBACKS` and `tokens.css`'s
 * `.dark` block. Change a dark colour and all three have to move together.
 */
const DARK_LITERALS: Record<ChartTokenName, string> = {
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

/** The `<script>` half of the chart SFC — where every `ctx.fillStyle` lives. */
const timelineScript = (() => {
  const sfc = read("../components/liquidity/TimelineChart.vue");
  const start = sfc.indexOf("<script");
  const end = sfc.indexOf("</script>");
  expect(start).toBeGreaterThanOrEqual(0);
  expect(end).toBeGreaterThan(start);
  return sfc.slice(start, end);
})();

/** A resolved colour a `<canvas>` will accept: `#rgb`…`#rrggbbaa`, `rgb()`, `rgba()`. */
const COLOUR = /^(#[0-9a-fA-F]{3,8}|rgba?\([^)]*\))$/;

/**
 * `--chart-*` declarations, per theme block.
 *
 * `tokens.css` now carries two full sets — the light palette on `:root` and
 * the dark one on `.dark` — so a single flat scan would silently keep only
 * whichever came last.
 */
const chartTokensIn = (selector: ":root" | ".dark") => {
  const css = read("../assets/tokens.css");
  const start = css.indexOf(`${selector} {`);
  expect(start, `no ${selector} block in tokens.css`).toBeGreaterThanOrEqual(0);
  const block = css.slice(start, css.indexOf("\n}", start));
  const found = new Map<string, string>();
  // Both groups are guaranteed by the pattern, so the assertions are safe.
  for (const match of block.matchAll(/--chart-([a-z0-9-]+)\s*:\s*([^;]+);/g)) {
    found.set(match[1]!, match[2]!.trim());
  }
  return found;
};

const lightTokens = chartTokensIn(":root");
const darkTokens = chartTokensIn(".dark");

afterEach(() => {
  resetChartTokenCache();
  Reflect.deleteProperty(globalThis, "document");
  Reflect.deleteProperty(globalThis, "getComputedStyle");
});

describe("chartTokens", () => {
  it("covers all 32 canvas colours", () => {
    expect(NAMES).toHaveLength(32);
  });

  describe("without a DOM", () => {
    it("returns the fallback for every name", () => {
      expect(typeof document).toBe("undefined");
      for (const name of NAMES) {
        expect(chartToken(name)).toBe(CHART_FALLBACKS[name]);
      }
    });

    it("never throws, even for a name that is not in the table", () => {
      expect(() => chartToken("nope" as ChartTokenName)).not.toThrow();
    });
  });

  describe("the fallbacks are the dark theme's literals", () => {
    it("matches the table this file keeps", () => {
      expect(CHART_FALLBACKS).toEqual(DARK_LITERALS);
    });

    it("is what tokens.css declares under .dark", () => {
      expect([...darkTokens.keys()].sort()).toEqual([...NAMES].sort());
      for (const name of NAMES) {
        expect(darkTokens.get(name), name).toBe(CHART_FALLBACKS[name]);
      }
    });
  });

  describe("tokens.css carries a colour for both themes", () => {
    it.each([
      [":root", lightTokens],
      [".dark", darkTokens],
    ])("declares all 32 --chart-* names in %s", (_selector, declared) => {
      expect([...declared.keys()].sort()).toEqual([...NAMES].sort());
    });

    it.each([
      [":root", lightTokens],
      [".dark", darkTokens],
    ])("declares a resolved colour string in %s", (_selector, declared) => {
      for (const name of NAMES) {
        const value = declared.get(name) ?? "";
        expect(value, name).not.toBe("");
        expect(value, `${name} = ${value}`).toMatch(COLOUR);
      }
    });

    it("gives the light theme its own palette, not the dark one", () => {
      const shared = NAMES.filter((name) => lightTokens.get(name) === darkTokens.get(name));
      expect(shared).toEqual([]);
    });
  });

  describe("TimelineChart reads the tokens rather than literals (E1)", () => {
    it("calls chartToken() once for every name", () => {
      const called = [...timelineScript.matchAll(/chartToken\('([\w-]+)'\)/g)].map(
        (match) => match[1]!,
      );
      expect([...called].sort()).toEqual([...NAMES].sort());
    });

    it("assigns no colour literal to the canvas any more", () => {
      const literals = timelineScript.match(
        /ctx\.(?:fill|stroke)Style = [^\n]*'(?:#[0-9a-fA-F]{3,8}|rgba?\([^)]*\))'/g,
      );
      expect(literals).toBeNull();
    });
  });

  describe("with a DOM", () => {
    /** Install a document whose custom properties answer from `values`. */
    const fakeDom = (values: Record<string, string>) => {
      const calls: string[] = [];
      Object.defineProperty(globalThis, "document", {
        value: { documentElement: {} },
        configurable: true,
      });
      Object.defineProperty(globalThis, "getComputedStyle", {
        value: () => ({
          getPropertyValue: (property: string) => {
            calls.push(property);
            return values[property] ?? "";
          },
        }),
        configurable: true,
      });
      return calls;
    };

    it("prefers the resolved custom property over the fallback", () => {
      fakeDom({ "--chart-bg": "  #123456  " });
      expect(chartToken("bg")).toBe("#123456");
    });

    it("asks the stylesheet for --chart-<name>", () => {
      const calls = fakeDom({});
      chartToken("day-hover");
      expect(calls).toEqual(["--chart-day-hover"]);
    });

    it("falls back when the property resolves empty", () => {
      fakeDom({});
      expect(chartToken("grid")).toBe(CHART_FALLBACKS.grid);
    });

    it("resolves once and serves the cache after that", () => {
      const calls = fakeDom({ "--chart-bg": "#111111" });
      expect(chartToken("bg")).toBe("#111111");
      expect(chartToken("bg")).toBe("#111111");
      expect(chartToken("bg")).toBe("#111111");
      expect(calls).toEqual(["--chart-bg"]);
    });

    it("re-reads after resetChartTokenCache()", () => {
      fakeDom({ "--chart-bg": "#111111" });
      expect(chartToken("bg")).toBe("#111111");
      resetChartTokenCache();
      const calls = fakeDom({ "--chart-bg": "#222222" });
      expect(chartToken("bg")).toBe("#222222");
      expect(calls).toEqual(["--chart-bg"]);
    });

    it("never throws when getComputedStyle does", () => {
      Object.defineProperty(globalThis, "document", {
        value: { documentElement: {} },
        configurable: true,
      });
      Object.defineProperty(globalThis, "getComputedStyle", {
        value: () => {
          throw new Error("detached document");
        },
        configurable: true,
      });
      expect(chartToken("bg")).toBe(CHART_FALLBACKS.bg);
    });
  });
});
