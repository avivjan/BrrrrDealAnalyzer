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

/** The `<script>` half of the chart SFC — where every `ctx.fillStyle` lives. */
const timelineScript = (() => {
  const sfc = read("../components/liquidity/TimelineChart.vue");
  const start = sfc.indexOf("<script");
  const end = sfc.indexOf("</script>");
  expect(start).toBeGreaterThanOrEqual(0);
  expect(end).toBeGreaterThan(start);
  return sfc.slice(start, end);
})();

/** `--chart-*` declarations as `tokens.css` writes them. */
const cssTokens = (() => {
  const css = read("../assets/tokens.css");
  const found = new Map<string, string>();
  // Both groups are guaranteed by the pattern, so the assertions are safe.
  for (const match of css.matchAll(/--chart-([a-z0-9-]+)\s*:\s*([^;]+);/g)) {
    found.set(match[1]!, match[2]!.trim());
  }
  return found;
})();

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

  describe("the fallbacks are today's literals", () => {
    it("every fallback appears verbatim in TimelineChart's script block", () => {
      const missing = NAMES.filter(
        (name) => !timelineScript.includes(CHART_FALLBACKS[name]),
      );
      expect(missing).toEqual([]);
    });

    it("every fallback has a matching --chart-* declaration in tokens.css", () => {
      expect([...cssTokens.keys()].sort()).toEqual([...NAMES].sort());
      for (const name of NAMES) {
        expect(cssTokens.get(name)).toBe(CHART_FALLBACKS[name]);
      }
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
