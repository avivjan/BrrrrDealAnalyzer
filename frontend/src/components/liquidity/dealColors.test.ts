import { describe, expect, it } from "vitest";

import type { LiquidityTransaction } from "../../types/liquidity";
import {
  assignDealColorSlotByDealKey,
  DEAL_COLOR_HEX_BY_SLOT_DARK_MODE,
  DEAL_COLOR_HEX_BY_SLOT_LIGHT_MODE,
  DEAL_COLOR_SLOT_COUNT,
  dealColorHexForSlot,
  dealKeyOf,
  dealKeyOfTransaction,
  NEUTRAL_DEAL_COLOR_HEX,
  shortDealAddress,
} from "./dealColors";

const dealKeys = (count: number) => Array.from({ length: count }, (_, index) => dealKeyOf("my_deals", `deal-${index + 1}`));

describe("assignDealColorSlotByDealKey", () => {
  it("gives the same deals the same colors, whatever their order", () => {
    const keys = dealKeys(4);
    const first = assignDealColorSlotByDealKey(keys);
    const second = assignDealColorSlotByDealKey([...keys].reverse());
    for (const key of keys) expect(second.get(key)).toBe(first.get(key));
  });

  it("gives up to six deals six different colors", () => {
    const slots = [...assignDealColorSlotByDealKey(dealKeys(DEAL_COLOR_SLOT_COUNT)).values()];
    expect(new Set(slots).size).toBe(DEAL_COLOR_SLOT_COUNT);
    expect(slots.every((slot) => slot !== null)).toBe(true);
  });

  it("gives a seventh deal the neutral color rather than a repeated hue", () => {
    const slots = [...assignDealColorSlotByDealKey(dealKeys(DEAL_COLOR_SLOT_COUNT + 1)).values()];
    expect(slots.filter((slot) => slot === null)).toHaveLength(1);
  });

  it("keeps a deal's color when another deal is added and does not collide with it", () => {
    const before = assignDealColorSlotByDealKey(dealKeys(1));
    const onlyKey = dealKeys(1)[0]!;
    // Find a second deal whose preferred slot differs, so no probe moves anyone.
    const candidates = Array.from({ length: 30 }, (_, index) => dealKeyOf("bought", `other-${index}`));
    const added = candidates.find((key) => {
      const both = assignDealColorSlotByDealKey([onlyKey, key]);
      return both.get(key) !== before.get(onlyKey) && assignDealColorSlotByDealKey([key]).get(key) === both.get(key);
    })!;
    expect(assignDealColorSlotByDealKey([onlyKey, added]).get(onlyKey)).toBe(before.get(onlyKey));
  });
});

describe("dealColorHexForSlot", () => {
  it("reads the slot's hue in the active mode and the neutral color for no slot", () => {
    expect(dealColorHexForSlot(0, "light")).toBe(DEAL_COLOR_HEX_BY_SLOT_LIGHT_MODE[0]);
    expect(dealColorHexForSlot(0, "dark")).toBe(DEAL_COLOR_HEX_BY_SLOT_DARK_MODE[0]);
    expect(dealColorHexForSlot(null, "dark")).toBe(NEUTRAL_DEAL_COLOR_HEX);
  });
});

describe("dealKeyOfTransaction", () => {
  const row = (over: Partial<LiquidityTransaction>): LiquidityTransaction => ({
    id: "t", effective_date: "2026-09-04", description: "Row", amount_dollars: -1, ...over,
  });

  it("is the deal's board and id for an imported row", () => {
    expect(dealKeyOfTransaction(row({ source_deal_board: "bought", source_deal_id: "d1" }))).toBe("bought:d1");
  });

  it("is null for a manual row and for a recurring occurrence", () => {
    expect(dealKeyOfTransaction(row({}))).toBeNull();
    expect(dealKeyOfTransaction(row({ recurring_rule_id: "r1", source_deal_board: "bought", source_deal_id: "d1" }))).toBeNull();
  });
});

describe("shortDealAddress", () => {
  it("keeps the street line", () => {
    expect(shortDealAddress("4431 Victor St, Jacksonville, FL 32207")).toBe("4431 Victor St");
    expect(shortDealAddress("1 Main St")).toBe("1 Main St");
  });
});
