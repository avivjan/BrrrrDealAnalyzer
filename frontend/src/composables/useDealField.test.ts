import { describe, expect, it } from "vitest";

import { useDealField } from "./useDealField";
import type { DealInputModel } from "../types";

describe("useDealField", () => {
  it("reads API strings as numbers and keeps zero", () => {
    const f = useDealField({ purchasePrice: "200.00", montly_hoa: "0.00" } as unknown as DealInputModel);
    expect(f.get("purchasePrice")).toBe(200);
    expect(f.get("montly_hoa")).toBe(0);
    expect(f.get("rent")).toBeNull();
  });

  it("set clears to undefined, setNullable keeps null", () => {
    const deal: DealInputModel = { recordingTransferBuy: 5, appliances: 630 } as DealInputModel;
    const f = useDealField(deal);
    f.set("appliances", null);
    f.setNullable("recordingTransferBuy", null);
    expect(deal.appliances).toBeUndefined();
    expect(deal.recordingTransferBuy).toBeNull();
    expect("recordingTransferBuy" in deal).toBe(true);
  });

  it("booleans fall back only when unset; strings drop empties", () => {
    const deal = {} as DealInputModel;
    const f = useDealField(deal);
    expect(f.getBool("onlineNotaryBuy", true)).toBe(true);
    f.setBool("onlineNotaryBuy", false);
    expect(f.getBool("onlineNotaryBuy", true)).toBe(false);
    f.setStr("buyClosingDate", "");
    expect(f.getStr("buyClosingDate")).toBeNull();
    f.setStr("buyClosingDate", "2026-01-10");
    expect(f.getStr("buyClosingDate")).toBe("2026-01-10");
  });
});
