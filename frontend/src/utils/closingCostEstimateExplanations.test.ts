import { describe, expect, it } from "vitest";
import { titleEscrowBuyItemizedDefault } from "./brrrAutoCalc";
import {
  recordingTransferBuyEstimateExplanationLines,
  recordingTransferRefiEstimateExplanationLines,
  titleEscrowBuyEstimateExplanationLines,
  titleEscrowRefiEstimateExplanationLines,
} from "./closingCostEstimateExplanations";

describe("closing-cost estimate explanations", () => {
  it("itemizes the Florida title estimate on a $100k purchase with a $123k loan when we pay all", () => {
    expect(titleEscrowBuyEstimateExplanationLines(titleEscrowBuyItemizedDefault("we_pay_all", 100_000, 123_000))).toEqual([
      "Office fees $600: $350 settlement + $150 title search + $100 municipal lien search",
      "Owner's policy $575: FL promulgated rate (F.A.C. 69O-186.003), $100,000 ÷ $1,000 × $5.75",
      "Lender's policy $365: $250 endorsements (ALTA 8.1, Form 9, simultaneous issue) + $5.00 per $1,000 of the $23,000 loan above the price",
    ]);
  });

  it("says the seller pays the owner's policy on a standard deal, and the lender's base when the loan fits the price", () => {
    const lines = titleEscrowBuyEstimateExplanationLines(titleEscrowBuyItemizedDefault("standard", 100_000, 90_000));
    expect(lines[1]).toBe("Owner's policy $0: the seller pays it on a standard deal");
    expect(lines[2]).toBe("Lender's policy $250: $250 endorsements (ALTA 8.1, Form 9, simultaneous issue); the loan does not exceed the price");
  });

  it("names both owner's-policy tiers above $100k", () => {
    expect(titleEscrowBuyEstimateExplanationLines(titleEscrowBuyItemizedDefault("we_pay_all", 250_000, 250_000))[1]).toBe(
      "Owner's policy $1,325: FL promulgated rate (F.A.C. 69O-186.003), $575 on the first $100,000 + $5.00 per $1,000 above",
    );
  });

  it("explains the buy recording default with the deal's numbers", () => {
    const lines = recordingTransferBuyEstimateExplanationLines(123_000, 0, 926.5);
    expect(lines[0]).toBe("$250 + 0.55% × $123,000 + $0 = $926.50");
    expect(lines[2]).toBe("No deed transfer tax: the seller pays it on a standard deal");
    expect(recordingTransferBuyEstimateExplanationLines(123_000, 700, 1626.5)[2]).toBe("+ the 0.70% deed transfer tax, because we pay all closing costs");
  });

  it("explains the refi recording and title defaults", () => {
    expect(recordingTransferRefiEstimateExplanationLines(180_000, 1240)[0]).toBe("0.55% × $180,000 refi loan + $250 = $1,240");
    expect(titleEscrowRefiEstimateExplanationLines(180_000, 1610)[0]).toBe("$800 + 0.45% × $180,000 refi loan = $1,610");
  });

  it("returns nothing while the numbers are missing", () => {
    expect(titleEscrowBuyEstimateExplanationLines(null)).toEqual([]);
    expect(recordingTransferBuyEstimateExplanationLines(null, 0, null)).toEqual([]);
    expect(recordingTransferRefiEstimateExplanationLines(null, null)).toEqual([]);
    expect(titleEscrowRefiEstimateExplanationLines(null, null)).toEqual([]);
  });
});
