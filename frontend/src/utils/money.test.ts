import { describe, expect, it } from "vitest";

import { formatMoney, parseMoney, toEditableText } from "./money";

/** Fields stored in thousands get the shorthand; dollar fields don't. */
const asThousandsField = (raw: string) => parseMoney(raw, true).dollars;
const asDollarField = (raw: string) => parseMoney(raw, false).dollars;

describe("parseMoney", () => {
  describe("a field stored in thousands", () => {
    it.each([
      // The fast path this whole feature exists to preserve.
      ["50", 50_000],
      ["200", 200_000],
      // ...and the granularity it exists to add. `50` used to round the field
      // to whole thousands, so $50,500 was simply unreachable.
      ["50.5", 50_500],
      ["50.505", 50_505],
      // Four digits or more is unambiguous: they typed the whole amount.
      ["50500", 50_500],
      ["1250000", 1_250_000],
      // A separator says the same thing.
      ["50,500", 50_500],
      ["1,250,000", 1_250_000],
      // Explicit units.
      ["50k", 50_000],
      ["50K", 50_000],
      ["50.5k", 50_500],
      ["1.2m", 1_200_000],
      ["1.2M", 1_200_000],
      // The escape hatch for a genuinely small amount.
      ["$800", 800],
      ["800$", 800],
      // Formatted text round-trips, which matters because the field shows it.
      ["$50,500", 50_500],
    ])("reads %j as $%d", (raw, expected) => {
      expect(asThousandsField(raw)).toBe(expected);
    });

    it("treats the 1,000 boundary as literal, not as thousands", () => {
      expect(asThousandsField("999")).toBe(999_000);
      expect(asThousandsField("1000")).toBe(1_000);
    });
  });

  describe("a field stored in dollars", () => {
    it("never applies the thousands shorthand", () => {
      // A $50 monthly HOA must stay $50. This is why the rule is opt-in.
      expect(asDollarField("50")).toBe(50);
      expect(asDollarField("2600")).toBe(2_600);
      expect(asDollarField("50.5")).toBe(50.5);
    });

    it("still honours an explicit k/m suffix", () => {
      expect(asDollarField("2.6k")).toBe(2_600);
    });
  });

  describe("empty and malformed input", () => {
    it.each(["", "   ", "abc", "$", "--"])("reads %j as null", (raw) => {
      expect(asThousandsField(raw)).toBeNull();
    });

    it("reports zero as a real zero, not as empty", () => {
      expect(asThousandsField("0")).toBe(0);
    });
  });

  it("flags whether the number was scaled, so the hint can stay quiet", () => {
    // The UI only echoes "= $50,000" back when it actually reinterpreted
    // something; repeating a number the user typed in full is just noise.
    expect(parseMoney("50", true).scaled).toBe(true);
    expect(parseMoney("50k", true).scaled).toBe(true);
    expect(parseMoney("50500", true).scaled).toBe(false);
    expect(parseMoney("$800", true).scaled).toBe(false);
  });

  it("does not leave float dust behind after scaling", () => {
    // 50.505 * 1000 is 50504.999999999996 in binary floating point.
    expect(asThousandsField("50.505")).toBe(50_505);
    expect(asThousandsField("1.115k")).toBe(1_115);
  });
});

describe("formatMoney", () => {
  it.each([
    [50_000, "$50,000"],
    [50_500, "$50,500"],
    [1_200_000, "$1,200,000"],
    [0, "$0"],
  ])("renders %d as %j", (value, expected) => {
    expect(formatMoney(value)).toBe(expected);
  });

  it("shows cents only when there are cents", () => {
    expect(formatMoney(50_500.25)).toBe("$50,500.25");
    expect(formatMoney(50_500)).toBe("$50,500");
  });

  it("renders an absent value as empty rather than $0", () => {
    expect(formatMoney(null)).toBe("");
    expect(formatMoney(undefined)).toBe("");
  });
});

describe("toEditableText", () => {
  it("strips the formatting so the caret has nothing to fight", () => {
    expect(toEditableText(50_500)).toBe("50500");
    expect(toEditableText(null)).toBe("");
  });
});
