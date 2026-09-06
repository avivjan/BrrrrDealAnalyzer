import { describe, expect, it } from "vitest";

import {
  DAY_WIDTH,
  PAD_LEFT,
  areaPath,
  balanceRange,
  clampScroll,
  formatK,
  indexForOffsetX,
  linePath,
  nextIndex,
  niceGridSteps,
  scrollToReveal,
  splitAtZero,
  visibleRange,
  xForIndex,
  yForBalance,
} from "./geometry";

describe("chart geometry", () => {
  it("pads the balance range by 12% and always reaches zero", () => {
    expect(balanceRange([])).toEqual({ min: 0, max: 100 });
    const r = balanceRange([10, 50]);
    expect(r.min).toBe(0);
    expect(r.max).toBe(55); // pad = max(12% of 40, 5) = 5
    expect(balanceRange([-10, 10]).min).toBeLessThan(-10);
  });

  it("maps days to x and back", () => {
    expect(xForIndex(0, 0)).toBe(PAD_LEFT + DAY_WIDTH / 2);
    expect(indexForOffsetX(xForIndex(3, 0), 0, 10)).toBe(3);
    expect(indexForOffsetX(10, 0, 10)).toBeNull();
    expect(indexForOffsetX(xForIndex(12, 0), 0, 10)).toBeNull();
    expect(indexForOffsetX(xForIndex(3, 96), 96, 10)).toBe(3);
  });

  it("maps balances to y within the plot area", () => {
    const range = { min: 0, max: 100 };
    expect(yForBalance(100, 200, range)).toBe(40);
    expect(yForBalance(0, 200, range)).toBe(200 - 52);
  });

  it("clamps scroll and reveals a day only when it would leave the view", () => {
    expect(clampScroll(-50, 10, 300)).toBe(0);
    expect(clampScroll(10_000, 10, 300)).toBe(PAD_LEFT + 10 * DAY_WIDTH + 24 - 300);
    expect(scrollToReveal(2, 0, 600, 100)).toBe(0);
    expect(scrollToReveal(40, 0, 600, 100)).toBeGreaterThan(0);
  });

  it("renders a window of days around the scroll, never outside the series", () => {
    expect(visibleRange(0, 480, 0)).toEqual([0, -1]);
    const [first, last] = visibleRange(0, 480, 100);
    expect(first).toBe(0);
    expect(last).toBe(13);
    expect(visibleRange(10_000, 480, 100)[1]).toBe(99);
  });

  it("keeps the keyboard contract: first press lands on 0, then steps and clamps", () => {
    expect(nextIndex(null, "ArrowRight", 5)).toBe(0);
    expect(nextIndex(null, "ArrowLeft", 5)).toBe(0);
    expect(nextIndex(2, "ArrowRight", 5)).toBe(3);
    expect(nextIndex(4, "ArrowRight", 5)).toBe(4);
    expect(nextIndex(0, "ArrowLeft", 5)).toBe(0);
    expect(nextIndex(2, "Enter", 5)).toBeNull();
    expect(nextIndex(null, "ArrowRight", 0)).toBeNull();
  });

  it("picks nice grid steps and formats thousands", () => {
    expect(niceGridSteps(0, 100, 6)).toEqual([0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100]);
    const wide = niceGridSteps(0, 250, 6);
    expect(wide[0]).toBe(0);
    expect(wide[1]! - wide[0]!).toBe(20);
    expect(wide[wide.length - 1]).toBeLessThanOrEqual(250);
    expect(niceGridSteps(5, 5, 6)).toEqual([0]);
    expect(formatK(12.34)).toBe("12.3k");
    expect(formatK(1500)).toBe("1.5M");
  });
});

describe("line + area paths", () => {
  it("linePath: empty → '', one point → a lone M, two points → M then L", () => {
    expect(linePath([])).toBe("");
    expect(linePath([{ x: 1, y: 2 }])).toBe("M1.0,2.0");
    expect(linePath([{ x: 1, y: 2 }, { x: 3.25, y: 4 }])).toBe("M1.0,2.0 L3.3,4.0");
  });

  it("areaPath: empty → '', otherwise the line closed down to the baseline and back", () => {
    expect(areaPath([], 10)).toBe("");
    expect(areaPath([{ x: 1, y: 2 }], 10)).toBe("M1.0,2.0 L1.0,10.0 L1.0,10.0 Z");
    expect(areaPath([{ x: 1, y: 2 }, { x: 5, y: 4 }], 10)).toBe("M1.0,2.0 L5.0,4.0 L5.0,10.0 L1.0,10.0 Z");
  });

  it("splitAtZero: one run per sign, sharing the interpolated crossing point", () => {
    expect(splitAtZero([])).toEqual([]);
    const same = splitAtZero([{ x: 0, y: 0, value: 5 }, { x: 10, y: 5, value: 0 }]);
    expect(same).toHaveLength(1);
    expect(same[0]!.positive).toBe(true);
    expect(same[0]!.points).toHaveLength(2);

    const runs = splitAtZero([
      { x: 0, y: 0, value: 10 },
      { x: 10, y: 20, value: -10 },
      { x: 20, y: 30, value: -20 },
      { x: 30, y: 10, value: 20 },
    ]);
    expect(runs.map((r) => r.positive)).toEqual([true, false, true]);
    expect(runs.map((r) => [r.first, r.last])).toEqual([[0, 0], [1, 2], [3, 3]]);
    // The crossing between samples 0 and 1 sits halfway: it ends run 0 and starts run 1.
    expect(runs[0]!.points).toEqual([{ x: 0, y: 0 }, { x: 5, y: 10 }]);
    expect(runs[1]!.points[0]).toEqual({ x: 5, y: 10 });
    expect(runs[1]!.points).toHaveLength(4);
    expect(runs[2]!.points[0]).toEqual({ x: 25, y: 20 });
  });
});
