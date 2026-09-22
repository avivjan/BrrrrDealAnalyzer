import { describe, expect, it } from "vitest";

import {
  formatCalculationStepMoney,
  formatCalculationStepPercent,
  formatCalculationStepRatio,
  formatCalculationStepValueByUnit,
} from "./calculationStepFormat";

describe("calculationStepFormat", () => {
  it("formats money with thousands separators, cents only when the amount has them", () => {
    expect(formatCalculationStepMoney(150000)).toBe("$150,000");
    expect(formatCalculationStepMoney(1234.5)).toBe("$1,234.50");
    expect(formatCalculationStepMoney(-26587)).toBe("-$26,587");
    expect(formatCalculationStepMoney(0)).toBe("$0");
  });

  it("formats percentages with two decimals and decodes the ±∞ sentinels", () => {
    expect(formatCalculationStepPercent(19.874)).toBe("19.87%");
    expect(formatCalculationStepPercent(-1)).toBe("∞%");
    expect(formatCalculationStepPercent(-2)).toBe("-∞%");
  });

  it("formats ratios as a multiple", () => {
    expect(formatCalculationStepRatio(1.2)).toBe("1.20x");
  });

  it("dispatches on the unit and treats a missing unit as money, never decoding money sentinels", () => {
    expect(formatCalculationStepValueByUnit("money", 85.04)).toBe("$85.04");
    expect(formatCalculationStepValueByUnit("pct", -1)).toBe("∞%");
    expect(formatCalculationStepValueByUnit("ratio", 1.234)).toBe("1.23x");
    expect(formatCalculationStepValueByUnit(undefined, -1)).toBe("-$1");
  });
});
