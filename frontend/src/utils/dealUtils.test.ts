import { describe, expect, it } from "vitest";

import { formatDealForClipboard, toNumber } from "./dealUtils";
import type { ActiveDealRes } from "../types";

describe("toNumber", () => {
  it("passes real numbers through, including zero", () => {
    expect(toNumber(200)).toBe(200);
    expect(toNumber(0)).toBe(0);
    expect(toNumber(-3.5)).toBe(-3.5);
  });

  it("parses the decimal strings the API actually sends", () => {
    // FastAPI serialises every Decimal column this way.
    expect(toNumber("200.00")).toBe(200);
    expect(toNumber("0.00")).toBe(0);
    expect(toNumber("6.75")).toBe(6.75);
  });

  it("returns undefined for anything not numeric, so callers can fall back", () => {
    expect(toNumber(null)).toBeUndefined();
    expect(toNumber(undefined)).toBeUndefined();
    expect(toNumber("")).toBeUndefined();
    expect(toNumber("   ")).toBeUndefined();
    expect(toNumber("abc")).toBeUndefined();
    expect(toNumber(NaN)).toBeUndefined();
    expect(toNumber({})).toBeUndefined();
  });
});

describe("formatDealForClipboard", () => {
  /** A saved FLIP deal in the exact shape `/active-deals` returns. */
  const savedFlip = {
    id: "abc",
    deal_type: "FLIP",
    address: "2286 Laurel Grove Ln W",
    purchasePrice: "200.00",
    rehabCost: "50.00",
    rehabContingency: "10.00",
    closingCostsBuy: "5.00",
    down_payment: "20.00",
    hmlPoints: "2.00",
    HMLInterestRate: "11.00",
    annual_property_taxes: "3600.00",
    annual_insurance: "1200.00",
    montly_hoa: "0.00",
    monthly_utilities: "250.00",
    salePrice: "320.00",
    holdingTime: 5,
    buyerAgentSellingFee: "3.00",
    sellerAgentSellingFee: "3.00",
    sellingClosingCosts: "5.00",
    capitalGainsTax: "20.00",
    use_HM_for_rehab: true,
    net_profit: "70010.00",
    roi: "95.14",
  } as unknown as ActiveDealRes;

  it("does not throw on a deal loaded from the API", () => {
    // Regression: money/percent fields arrive as strings, and `.toFixed()` on a
    // string threw, so "Copy Summary for AI" crashed for every saved deal.
    expect(() => formatDealForClipboard(savedFlip)).not.toThrow();
  });

  it("formats the string-valued fields as real numbers", () => {
    const summary = formatDealForClipboard(savedFlip);
    expect(summary).toContain("2286 Laurel Grove Ln W");
    expect(summary).toContain("$320");
    expect(summary).not.toContain("$320.00.00");
    expect(summary).not.toContain("undefined");
    expect(summary).not.toContain("NaN");
  });

  it("still works when the deal already holds real numbers", () => {
    const typed = { ...savedFlip, purchasePrice: 200, salePrice: 320 } as ActiveDealRes;
    expect(() => formatDealForClipboard(typed)).not.toThrow();
  });
});
