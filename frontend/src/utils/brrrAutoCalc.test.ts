import { describe, expect, it } from "vitest";

import {
  addDays,
  brrrAutoCalc,
  dayOfYear,
  daysBetween,
  daysThroughMonthEnd,
  parseIsoDate,
  sellerTaxCredit,
  titleEscrowBuyDefault,
} from "./brrrAutoCalc";
import type { DealInputModel } from "../types";

/**
 * The backend's `tests/conftest.py::brrrr_payload`, as the form emits it. The expected
 * numbers below are what `BackEnd/BL/analyze/analyzeBRRR.py` returns for it (dated
 * 2026-01-10, 181 days to refi): this is the parity contract between the inline
 * figures and the engine.
 */
const FIXTURE: DealInputModel = {
  deal_type: "BRRRR",
  purchasePrice: 200, rehabCost: 50, rehabContingency: 10, down_payment: 20, hmlPoints: 2, HMLInterestRate: 11,
  annual_property_taxes: 3600, annual_insurance: 1200, montly_hoa: 0, arv_in_thousands: 320, daysUntilRefi: 181,
  refiPoints: 1.5, loanTermYears: 30, ltv_as_precent: 75, interestRate: 6.5, rent: 2600, vacancyPercent: 5,
  property_managment_fee_precentages_from_rent: 8, maintenancePercent: 5, capexPercent: 5,
  buyClosingDate: "2026-01-10", earnestMoneyDeposit: 5000, loanChargesBuy: 900, recordingTransferBuy: null,
  titleModeBuy: "standard", titleEscrowBuy: null, onlineNotaryBuy: true, otherClosingCostsBuy: 0,
  sellerPaidCurrentYearTaxes: null, constructionLoanBudget: 55, rehabCushion: 5000, daysUntilRented: 90,
  monthlyUtilitiesUntilRented: 80, maintenanceBeforeRefi: 500, appliances: 630, loanChargesRefi: 200,
  recordingTransferRefi: null, titleEscrowRefi: null, onlineNotaryRefi: true, appraisalFee: 700, surveyFee: 385,
  refiUnderwritingFee: 2000, brokerProcessingFeeRefi: 395, otherClosingCostsRefi: 0, maintenanceReserve: 1500,
  vacancyReserve: null, capexReserve: 2500, lowestArv: null,
  section: 2, stage: 2, address: "1 Shared Form St",
};

const close = (actual: number | null, expected: number) => expect(actual).toBeCloseTo(expected, 2);

describe("brrrAutoCalc — parity with the backend engine", () => {
  const c = brrrAutoCalc(FIXTURE);

  it("the hard-money stack", () => {
    close(c.purchaseLoanAmount, 160_000);
    close(c.hmlAmount, 215_000);
    close(c.hmlPointsDollars, 4_300);
    close(c.totalHardMoneyCost, 4300 + 11890.69 + 900);
  });

  it("the interest timeline: 22 prepaid days, refi on Jul 10", () => {
    expect(c.prepaidDaysBuy).toBe(22);
    expect(c.refiClosingDate).toBe("2026-07-10");
    expect(c.tenantOccupiedDate).toBe("2026-04-10");
    close(c.prepaidInterestBuy, 1445.28);
    expect(c.prepaidDaysRefi).toBe(22);
    close(c.prepaidInterestRefi, 940.27);
  });

  it("the purchase settlement", () => {
    close(c.sellerTaxCredit, 88.77);
    expect(c.sellerPaidCurrentYearTaxesEffective).toBe(false);
    close(c.recordingTransferBuyEffective, 1130);
    close(c.titleEscrowBuyEffective, 1000);
    close(c.closingCostsBuyTotal, 3280);
    close(c.cashToCloseBuy, 43936.51);
  });

  it("the rehab draws and the holding period", () => {
    close(c.stolenMoney, 0);
    close(c.preRefiRentalIncome, 7886.67);
    close(c.utilitiesUntilRented, 240);
  });

  it("the refinance settlement and the two wires", () => {
    close(c.refiLoanAmount, 240_000);
    close(c.closingCostsRefiTotal, 10_980);
    close(c.reservesTotal, 6_600);
    close(c.lowestArvEffective, 288_000);
    close(c.cashOutWire, 5888.48);
    close(c.cashOutWireConservative, -17417.5);
  });
});

describe("brrrAutoCalc — figures appear only once their inputs exist", () => {
  it("is empty on an empty form", () => {
    const c = brrrAutoCalc({ deal_type: "BRRRR" } as DealInputModel);
    expect(c.purchaseLoanAmount).toBeNull();
    expect(c.cashToCloseBuy).toBeNull();
    expect(c.prepaidInterestBuy).toBeNull();
    expect(c.sellerTaxCredit).toBeNull();
    expect(c.cashOutWire).toBeNull();
    expect(c.refiClosingDate).toBeNull();
  });

  it("needs a closing date for the date-driven figures, and rent for the rent-driven ones", () => {
    const undated = brrrAutoCalc({ ...FIXTURE, buyClosingDate: null });
    expect(undated.prepaidInterestBuy).toBeNull();
    expect(undated.sellerTaxCredit).toBeNull();
    expect(undated.refiClosingDate).toBeNull();
    expect(undated.cashToCloseBuy).not.toBeNull(); // the wire still shows, without the dated lines
    expect(brrrAutoCalc({ ...FIXTURE, rent: 0 }).preRefiRentalIncome).toBeNull();
  });

  it("honours typed overrides of the formula defaults", () => {
    const c = brrrAutoCalc({ ...FIXTURE, recordingTransferBuy: 1234, lowestArv: 250, vacancyReserve: 0, titleModeBuy: "we_pay_all" });
    expect(c.recordingTransferBuyEffective).toBe(1234);
    expect(c.lowestArvEffective).toBe(250_000);
    expect(c.vacancyReserveEffective).toBe(0);
    expect(c.titleEscrowBuyEffective).toBe(2200);
  });

  it("flips the tax credit in December and with the override", () => {
    expect(brrrAutoCalc({ ...FIXTURE, buyClosingDate: "2026-12-15" }).sellerTaxCredit!).toBeLessThan(0);
    expect(brrrAutoCalc({ ...FIXTURE, buyClosingDate: "2026-11-20" }).sellerTaxCredit!).toBeGreaterThan(0);
    expect(brrrAutoCalc({ ...FIXTURE, buyClosingDate: "2026-11-20", sellerPaidCurrentYearTaxes: true }).sellerTaxCredit!).toBeLessThan(0);
  });
});

describe("date helpers", () => {
  it("parses only real ISO calendar dates", () => {
    expect(parseIsoDate("2026-02-29")).toBeNull();
    expect(parseIsoDate("2024-02-29")).not.toBeNull();
    expect(parseIsoDate("10/01/2026")).toBeNull();
    expect(parseIsoDate("")).toBeNull();
  });
  it("adds and subtracts whole days", () => {
    expect(addDays("2026-01-10", 181)).toBe("2026-07-10");
    expect(daysBetween("2026-01-10", "2026-07-10")).toBe(181);
    expect(daysBetween("2026-07-10", "2026-01-10")).toBe(-181);
  });
  it("counts the prepaid window and the day of the year", () => {
    expect(daysThroughMonthEnd(parseIsoDate("2026-01-10")!)).toBe(22);
    expect(daysThroughMonthEnd(parseIsoDate("2024-02-01")!)).toBe(29);
    expect(dayOfYear(parseIsoDate("2026-07-01")!)).toBe(182);
  });
  it("prorates taxes on the calendar year", () => {
    expect(sellerTaxCredit(3650, parseIsoDate("2026-07-01")!, false)).toBeCloseTo((3650 * 181) / 365, 6);
    expect(sellerTaxCredit(3650, parseIsoDate("2026-12-15")!, true)).toBeCloseTo((-3650 * 17) / 365, 6);
    expect(sellerTaxCredit(3650, parseIsoDate("2024-02-29")!, false)).toBeCloseTo((3650 * 59) / 366, 6);
  });
  it.each([[149_999, 2050], [150_000, 2200], [200_000, 2200], [200_001, 2400]])("we-pay-all title tier at $%s is $%s", (price, fee) => {
    expect(titleEscrowBuyDefault("we_pay_all", price)).toBe(fee);
  });
});
