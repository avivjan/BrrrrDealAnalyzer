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

const expectCloseToTheCent = (actual: number | null, expected: number) => expect(actual).toBeCloseTo(expected, 2);

describe("brrrAutoCalc — parity with the backend engine", () => {
  const autoCalc = brrrAutoCalc(FIXTURE);

  it("the hard-money stack", () => {
    expectCloseToTheCent(autoCalc.purchaseLoanAmount, 160_000);
    expectCloseToTheCent(autoCalc.hmlAmount, 215_000);
    expectCloseToTheCent(autoCalc.hmlPointsDollars, 4_300);
    expectCloseToTheCent(autoCalc.totalHardMoneyCost, 4300 + 11890.69 + 900);
  });

  it("the interest timeline: 22 prepaid days, refi on Jul 10", () => {
    expect(autoCalc.prepaidDaysBuy).toBe(22);
    expect(autoCalc.refiClosingDate).toBe("2026-07-10");
    expect(autoCalc.tenantOccupiedDate).toBe("2026-04-10");
    expectCloseToTheCent(autoCalc.prepaidInterestBuy, 1445.28);
    expect(autoCalc.prepaidDaysRefi).toBe(22);
    expectCloseToTheCent(autoCalc.prepaidInterestRefi, 940.27);
  });

  it("the purchase settlement", () => {
    expectCloseToTheCent(autoCalc.sellerTaxCredit, 88.77);
    expect(autoCalc.sellerPaidCurrentYearTaxesEffective).toBe(false);
    expectCloseToTheCent(autoCalc.deedTransferTaxBuy, 0);
    expectCloseToTheCent(autoCalc.recordingTransferBuyEffective, 250 + 0.0055 * 215_000); // the WHOLE hard-money loan
    expectCloseToTheCent(autoCalc.titleEscrowBuyEffective, 1000);
    expectCloseToTheCent(autoCalc.closingCostsBuyTotal, 3582.5);
    expectCloseToTheCent(autoCalc.cashToCloseBuy, 44239.01);
  });

  it("the rehab draws and the holding period", () => {
    expectCloseToTheCent(autoCalc.stolenMoney, 0);
    expectCloseToTheCent(autoCalc.preRefiRentalIncome, 7886.67);
    expectCloseToTheCent(autoCalc.utilitiesUntilRented, 240);
  });

  it("the refinance settlement and the two wires", () => {
    expectCloseToTheCent(autoCalc.refiLoanAmount, 240_000);
    expectCloseToTheCent(autoCalc.closingCostsRefiTotal, 10_980);
    expectCloseToTheCent(autoCalc.reservesTotal, 6_600);
    expectCloseToTheCent(autoCalc.lowestArvEffective, 288_000);
    expectCloseToTheCent(autoCalc.cashOutWire, 5888.48);
    expectCloseToTheCent(autoCalc.cashOutWireConservative, -17417.5);
  });
});

describe("brrrAutoCalc — figures appear only once their inputs exist", () => {
  it("is empty on an empty form", () => {
    const autoCalc = brrrAutoCalc({ deal_type: "BRRRR" } as DealInputModel);
    expect(autoCalc.purchaseLoanAmount).toBeNull();
    expect(autoCalc.cashToCloseBuy).toBeNull();
    expect(autoCalc.prepaidInterestBuy).toBeNull();
    expect(autoCalc.sellerTaxCredit).toBeNull();
    expect(autoCalc.cashOutWire).toBeNull();
    expect(autoCalc.refiClosingDate).toBeNull();
  });

  it("needs a closing date for the date-driven figures, and rent for the rent-driven ones", () => {
    const withoutClosingDate = brrrAutoCalc({ ...FIXTURE, buyClosingDate: null });
    expect(withoutClosingDate.prepaidInterestBuy).toBeNull();
    expect(withoutClosingDate.sellerTaxCredit).toBeNull();
    expect(withoutClosingDate.refiClosingDate).toBeNull();
    expect(withoutClosingDate.cashToCloseBuy).not.toBeNull(); // the wire still shows, without the dated lines
    expect(brrrAutoCalc({ ...FIXTURE, rent: 0 }).preRefiRentalIncome).toBeNull();
  });

  it("we-pay-all adds the deed transfer tax to the recording default and shows the premium over standard", () => {
    const wePayAll = brrrAutoCalc({ ...FIXTURE, titleModeBuy: "we_pay_all" });
    expectCloseToTheCent(wePayAll.deedTransferTaxBuy, 0.007 * 200_000);
    expectCloseToTheCent(wePayAll.recordingTransferBuyEffective, 250 + 0.0055 * 215_000 + 1400);
    expectCloseToTheCent(wePayAll.titleEscrowBuyEffective, 2200);
    // the premium is the same whichever mode is selected: (2200 - 1000) + 1400
    expectCloseToTheCent(wePayAll.wePayAllExtraClosingCost, 2600);
    expectCloseToTheCent(brrrAutoCalc(FIXTURE).wePayAllExtraClosingCost, 2600);
  });

  it("the notary fee defaults to $250, can be typed, and is $0 when the checkbox is off", () => {
    expect(brrrAutoCalc(FIXTURE).notaryBuy).toBe(250);
    expect(brrrAutoCalc({ ...FIXTURE, onlineNotaryFeeBuy: 175 }).notaryBuy).toBe(175);
    expect(brrrAutoCalc({ ...FIXTURE, onlineNotaryFeeBuy: 175, onlineNotaryBuy: false }).notaryBuy).toBe(0);
    expect(brrrAutoCalc({ ...FIXTURE, onlineNotaryFeeRefi: 300 }).notaryRefi).toBe(300);
  });

  it("honours typed overrides of the formula defaults", () => {
    const autoCalc = brrrAutoCalc({ ...FIXTURE, recordingTransferBuy: 1234, lowestArv: 250, vacancyReserve: 0, titleModeBuy: "we_pay_all" });
    expect(autoCalc.recordingTransferBuyEffective).toBe(1234);
    expect(autoCalc.lowestArvEffective).toBe(250_000);
    expect(autoCalc.vacancyReserveEffective).toBe(0);
    expect(autoCalc.titleEscrowBuyEffective).toBe(2200);
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
