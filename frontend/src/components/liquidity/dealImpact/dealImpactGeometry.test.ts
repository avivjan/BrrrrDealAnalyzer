import { describe, expect, it } from "vitest";

import {
  gapPolygonPath,
  monthTicks,
  runsBelow,
  stackLabels,
  valueRangeFor,
  windowForRange,
  windowIndexForX,
  xForWindowIndex,
  yForValue,
} from "./dealImpactGeometry";

/** 400 days from Oct 1, 2026. */
const DATES = Array.from({ length: 400 }, (_, index) => new Date(Date.UTC(2026, 9, 1 + index)).toISOString().slice(0, 10));
const TODAY = "2026-11-03";

describe("windowForRange", () => {
  it("shows the deal's lifecycle: a week before today through 60 days after the refi", () => {
    const window = windowForRange(DATES, "deal_lifecycle", TODAY, { refiDate: "2027-03-03", lowestDate: "2026-12-15" });
    expect([DATES[window.first], DATES[window.last]]).toEqual(["2026-10-27", "2027-05-02"]);
  });

  it("reaches 30 days past a low point that comes after the refi", () => {
    const window = windowForRange(DATES, "deal_lifecycle", TODAY, { refiDate: "2026-12-01", lowestDate: "2027-04-01" });
    expect(DATES[window.last]).toBe("2027-05-01");
  });

  it("gives the fixed ranges from a week before today, and All the whole series, inside the series", () => {
    expect(DATES[windowForRange(DATES, "six_months", TODAY, { refiDate: null, lowestDate: null }).last]).toBe("2027-05-05");
    expect(DATES[windowForRange(DATES, "one_year", TODAY, { refiDate: null, lowestDate: null }).last]).toBe("2027-11-03");
    expect(windowForRange(DATES, "all", TODAY, { refiDate: null, lowestDate: null })).toEqual({ first: 0, last: 399 });
  });
});

describe("scales", () => {
  const box = { left: 60, right: 460, top: 20, bottom: 220 };
  const window = { first: 10, last: 110 };

  it("spreads the window over the plot's width, and maps an x back to its day", () => {
    expect(xForWindowIndex(10, window, box)).toBe(60);
    expect(xForWindowIndex(110, window, box)).toBe(460);
    expect(windowIndexForX(260, window, box)).toBe(60);
    expect(windowIndexForX(-50, window, box)).toBe(10);
  });

  it("keeps zero and the reserve inside the y range, with room", () => {
    const range = valueRangeFor([50_000, 50_000], [40_000, 45_000], { first: 0, last: 1 }, 5_000);
    expect(range.min).toBeLessThan(0);
    expect(range.max).toBeGreaterThan(50_000);
    expect(yForValue(range.min, range, box)).toBe(220);
    expect(yForValue(range.max, range, box)).toBe(20);
  });
});

describe("shapes", () => {
  it("closes the gap between the two lines along after, then back along before", () => {
    const path = gapPolygonPath([{ x: 0, y: 10 }, { x: 10, y: 10 }], [{ x: 0, y: 30 }, { x: 10, y: 40 }]);
    expect(path).toBe("M0.0,30.0 L10.0,40.0 L10.0,10.0 L0.0,10.0 Z");
    expect(gapPolygonPath([], [])).toBe("");
  });

  it("finds the runs under a line inside the window", () => {
    expect(runsBelow([10, 3, 2, 9, 1, 1, 8], 5, { first: 0, last: 6 })).toEqual([{ first: 1, last: 2 }, { first: 4, last: 5 }]);
    expect(runsBelow([1, 1, 1], 5, { first: 1, last: 2 })).toEqual([{ first: 1, last: 2 }]);
  });

  it("stacks labels that would overlap on the next row", () => {
    expect(stackLabels([{ x: 100, width: 60 }, { x: 120, width: 60 }, { x: 300, width: 60 }, { x: 140, width: 40 }])).toEqual([0, 1, 0, 2]);
  });

  it("ticks the 1sts of the months, with the year on January", () => {
    expect(monthTicks(DATES, { first: 0, last: 120 }).map((tick) => tick.label)).toEqual(["Oct", "Nov", "Dec", "Jan '27"]);
  });
});
