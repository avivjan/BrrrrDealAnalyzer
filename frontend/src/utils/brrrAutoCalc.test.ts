import { describe, expect, it } from "vitest";

import {
  addDays,
  annualPropertyTaxesFromSellerTaxCredit,
  brrrAutoCalc,
  dayOfYear,
  daysBetween,
  daysThroughMonthEnd,
  parseIsoDate,
  sellerTaxCredit,
  sellerTaxCreditProratedDays,
  titleEscrowBuyDefault,
  titleEscrowBuyItemizedDefault,
  floridaOwnersTitlePolicyPremium,
  lendersTitlePolicyAndEndorsements,
  wePayAllExtraClosingCost,
  currentYearPropertyTaxBillPaidAtPurchaseClosing,
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
  contractDate: "2026-01-03", buyClosingDate: "2026-01-10", earnestMoneyDeposit: 5000, loanChargesBuy: 900, recordingTransferBuy: null,
  titleModeBuy: "standard", titleEscrowBuy: null, onlineNotaryBuy: true, otherClosingCostsBuy: 0,
  sellerPaidCurrentYearTaxes: null, constructionLoanBudget: 55, rehabCushion: 5000, daysUntilRehabCompleted: 45, daysUntilRented: 90,
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
    expectCloseToTheCent(autoCalc.prepaidInterestRefi, 953.33); // 240,000 × 6.5% ÷ 360 × 22: the 360-day year of the refi statements
    expect(autoCalc.rehabCompletedDate).toBe("2026-02-24");
  });

  it("the purchase settlement", () => {
    expectCloseToTheCent(autoCalc.sellerTaxCredit, 88.77);
    expect(autoCalc.sellerPaidCurrentYearTaxesEffective).toBe(false);
    expectCloseToTheCent(autoCalc.deedTransferTaxBuy, 0);
    expectCloseToTheCent(autoCalc.recordingTransferBuyEffective, 250 + 0.0055 * 215_000); // the WHOLE hard-money loan
    expectCloseToTheCent(autoCalc.titleEscrowBuyEffective, 925); // $600 office fees + $250 + $15k above the price × $5/$1k
    expectCloseToTheCent(autoCalc.insuranceBillAtPurchaseInsideClosing, 1200);
    expectCloseToTheCent(autoCalc.closingCostsBuyTotal, 4707.5); // includes the $1,200 insurance bill paid inside the closing
    expectCloseToTheCent(autoCalc.cashToCloseBuy, 45364.01);
  });

  it("the tax bucket and the regular-year tax", () => {
    expect(autoCalc.firstPropertyTaxPaymentDate).toBe("2026-11-30");
    expect(autoCalc.propertyTaxBucketDepositCountUntilFirstPayment).toBe(11); // Jan 15 .. Nov 15
    expect(autoCalc.propertyTaxBucketFirstBillDepositCountUntilRefi).toBe(6); // Jan 15 .. Jun 15, before the Jul 10 refi
    expectCloseToTheCent(autoCalc.propertyTaxBucketDepositEffective, 306.11);
    expectCloseToTheCent(autoCalc.monthlyPropertyTaxAfterRefi, 288);
  });

  it("the rehab draws and the holding period", () => {
    expectCloseToTheCent(autoCalc.stolenMoney, 0);
    // Rent on May 1, Jun 1 and Jul 1 (tenant Apr 10, refi Jul 10); utilities on Feb 1 .. Apr 1 plus May 1 in arrears.
    expect(autoCalc.rentCollectionCountBeforeRefi).toBe(3);
    expectCloseToTheCent(autoCalc.preRefiRentalIncome, 7800);
    expectCloseToTheCent(autoCalc.utilitiesUntilRented, 320);
  });

  it("the refinance settlement and the two wires", () => {
    expectCloseToTheCent(autoCalc.refiLoanAmount, 240_000);
    // Appraisal and survey are paid outside the closing; the $1,200 insurance bill is paid inside it.
    expectCloseToTheCent(autoCalc.closingCostsRefiTotal, 11_095);
    expectCloseToTheCent(autoCalc.appraisalAndSurveyPaidOutsideClosing, 1085);
    expectCloseToTheCent(autoCalc.monthlyPrincipalAndInterest, 1516.96);
    expectCloseToTheCent(autoCalc.hysaDepositAtRefiEffective, 4550.89);
    expectCloseToTheCent(autoCalc.reservesTotal, 11_150.89);
    expectCloseToTheCent(autoCalc.monthlyInsuranceAfterRefiDefault, 100);
    expectCloseToTheCent(autoCalc.lowestArvEffective, 288_000);
    // The settlement statement's "Due to Borrower": the reserves are not taken off it.
    expectCloseToTheCent(autoCalc.cashOutWire, 12360.42);
    expectCloseToTheCent(autoCalc.cashOutWireConservative, -10944.25);
  });

  it("the insurance and tax pickers move the bills between the settlements and the pocket", () => {
    const outside = brrrAutoCalc({ ...FIXTURE, insurancePurchaseBillPaymentTiming: "outside_purchase_closing", insuranceRefiBillPaymentTiming: "outside_refi_closing" });
    expectCloseToTheCent(outside.closingCostsBuyTotal, 3507.5);
    expectCloseToTheCent(outside.cashOutWire, 12360.42 + 1200);
    const lenderCollectsTheTax = brrrAutoCalc({ ...FIXTURE, propertyTaxCollectionAtRefi: "full_tax_bill_collected_at_refi" });
    expectCloseToTheCent(lenderCollectsTheTax.propertyTaxLumpSumAtRefiClosingEffective, 3600);
    expectCloseToTheCent(lenderCollectsTheTax.cashOutWire, 12360.42 - 3600);
    expect(brrrAutoCalc({ ...FIXTURE, propertyTaxLumpSumAtRefiClosing: 3000 }).propertyTaxLumpSumAtRefiClosingEffective).toBe(0); // only with the lender option
  });

  it("a seller who already paid this year's bill sends the bucket to next year's Nov 30, from Dec 15", () => {
    const alreadyPaid = brrrAutoCalc({ ...FIXTURE, buyClosingDate: "2026-11-20", sellerPaidCurrentYearTaxes: true, daysUntilRefi: 120 });
    expect(alreadyPaid.firstPropertyTaxPaymentDate).toBe("2027-11-30");
    expect(alreadyPaid.propertyTaxBucketDepositCountUntilFirstPayment).toBe(12);
    expectCloseToTheCent(alreadyPaid.propertyTaxBucketDepositEffective, (3600 * 0.96) / 12);
    expect(alreadyPaid.propertyTaxBucketFirstBillDepositCountUntilRefi).toBe(4); // Dec 15 .. Mar 15, before the Mar 20 refi
    const notPaid = brrrAutoCalc({ ...FIXTURE, buyClosingDate: "2026-11-20", sellerPaidCurrentYearTaxes: false, daysUntilRefi: 120 });
    expect(notPaid.firstPropertyTaxPaymentDate).toBe("2026-11-30");
    expect(notPaid.propertyTaxBucketDepositCountUntilFirstPayment).toBe(1);
  });

  it("the settlement-statement seller credit overrides the proration and feeds the deposit", () => {
    const typedCredit = brrrAutoCalc({ ...FIXTURE, sellerTaxCreditAtPurchaseClosing: 120.45 });
    expectCloseToTheCent(typedCredit.sellerTaxCreditFormula, 88.77);
    expectCloseToTheCent(typedCredit.sellerTaxCredit, 120.45);
    expectCloseToTheCent(typedCredit.propertyTaxBucketDepositEffective, (3600 * 0.96 - 120.45) / 11);
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

  it("a refi on a 1st carries the month before it inside the payoff, and the monthly items count real 1sts", () => {
    // Closing Jan 10, refi Jul 1 (172 days): Feb .. May are paid on Mar 1 .. Jun 1; June's 30 days are in the payoff.
    const refiOnTheFirst = brrrAutoCalc({ ...FIXTURE, daysUntilRefi: 172, monthlyInsuranceUntilRefi: 90 });
    expectCloseToTheCent(refiOnTheFirst.hmlPayoff, refiOnTheFirst.hmlAmount! + refiOnTheFirst.hmlPerDiem! * 30);
    // Insurance on Feb 1 .. Jul 1 (the refi day counts).
    expectCloseToTheCent(refiOnTheFirst.insurancePaidMonthlyUntilRefi, 90 * 6);
    // A tenant after the refi: no rent, and utilities stop at the refi (Feb 1 .. Jul 1, no bill after it).
    const tenantAfterRefi = brrrAutoCalc({ ...FIXTURE, daysUntilRefi: 172, daysUntilRented: 200 });
    expect(tenantAfterRefi.rentCollectionCountBeforeRefi).toBe(0);
    expectCloseToTheCent(tenantAfterRefi.utilitiesUntilRented, 80 * 6);
  });

  it("needs rent for the rent-driven figures", () => {
    expect(brrrAutoCalc({ ...FIXTURE, rent: 0 }).preRefiRentalIncome).toBeNull();
  });

  it("we-pay-all adds the deed transfer tax to the recording default and shows the premium over standard", () => {
    const wePayAll = brrrAutoCalc({ ...FIXTURE, titleModeBuy: "we_pay_all" });
    expectCloseToTheCent(wePayAll.deedTransferTaxBuy, 0.007 * 200_000);
    expectCloseToTheCent(wePayAll.recordingTransferBuyEffective, 250 + 0.0055 * 215_000 + 1400);
    expectCloseToTheCent(wePayAll.titleEscrowBuyEffective, 2000); // 925 + the owner's policy on $200k ($575 + $500)
    // the premium is the same whichever mode is selected: the owner's policy 1075 + the deed tax 1400
    expectCloseToTheCent(wePayAll.wePayAllExtraClosingCost, 2475);
    expectCloseToTheCent(brrrAutoCalc(FIXTURE).wePayAllExtraClosingCost, 2475);
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
    expect(autoCalc.titleEscrowBuyEffective).toBeCloseTo(2000, 10); // untyped: the Florida estimate with the owner's policy
  });

  it("computes nothing from a lowest ARV that is above the ARV or not positive", () => {
    for (const lowestArv of [400, 0, -5]) {
      const autoCalc = brrrAutoCalc({ ...FIXTURE, lowestArv });
      expect(autoCalc.lowestArvEffective, `lowestArv ${lowestArv}`).toBeNull();
      expect(autoCalc.conservativeRefiLoanAmount).toBeNull();
      expect(autoCalc.cashOutWireConservative).toBeNull();
      expect(autoCalc.cashOutWire).not.toBeNull(); // the ARV-based figures are untouched
    }
    expect(brrrAutoCalc({ ...FIXTURE, lowestArv: 320 }).lowestArvEffective).toBe(320_000); // equal is allowed
    expect(brrrAutoCalc({ ...FIXTURE, arv_in_thousands: 0, lowestArv: 250 }).lowestArvEffective).toBe(250_000); // no ARV to compare against yet
  });

  it("flips the tax credit from October (the title takes the bill at closing) and with the override", () => {
    expect(brrrAutoCalc({ ...FIXTURE, buyClosingDate: "2026-12-15" }).sellerTaxCredit!).toBeLessThan(0);
    expect(brrrAutoCalc({ ...FIXTURE, buyClosingDate: "2026-10-01" }).sellerTaxCredit!).toBeLessThan(0);
    expect(brrrAutoCalc({ ...FIXTURE, buyClosingDate: "2026-09-30" }).sellerTaxCredit!).toBeGreaterThan(0);
    expect(brrrAutoCalc({ ...FIXTURE, buyClosingDate: "2026-09-30", sellerPaidCurrentYearTaxes: true }).sellerTaxCredit!).toBeLessThan(0);
    expect(brrrAutoCalc({ ...FIXTURE, buyClosingDate: "2026-11-20", sellerPaidCurrentYearTaxes: false }).sellerTaxCredit!).toBeGreaterThan(0);
  });

  it("an October closing whose bill the title took deposits for next year from Dec 15, 12 times", () => {
    const octoberFirst = brrrAutoCalc({ ...FIXTURE, buyClosingDate: "2026-10-01", daysUntilRefi: 120 });
    expect(octoberFirst.sellerPaidCurrentYearTaxesEffective).toBe(true);
    expect(octoberFirst.firstPropertyTaxPaymentDate).toBe("2027-11-30");
    expect(octoberFirst.propertyTaxBucketDepositCountUntilFirstPayment).toBe(12); // Dec 15, 2026 .. Nov 15, 2027: no Oct 15 or Nov 15
    expectCloseToTheCent(octoberFirst.propertyTaxBucketDepositEffective, (3600 * 0.96) / 12);
    expect(octoberFirst.propertyTaxBucketFirstBillDepositCountUntilRefi).toBe(2); // Dec 15 and Jan 15, before the Jan 29 refi
  });

  it("counts the days the tax proration covers", () => {
    expect(brrrAutoCalc(FIXTURE).sellerTaxCreditProratedDays).toBe(9); // Jan 1 .. Jan 9
    expect(brrrAutoCalc({ ...FIXTURE, buyClosingDate: "2026-12-15" }).sellerTaxCreditProratedDays).toBe(17); // Dec 15 .. Dec 31, seller paid
    expect(brrrAutoCalc({ ...FIXTURE, buyClosingDate: "2026-01-01" }).sellerTaxCreditProratedDays).toBe(0);
  });
});

describe("annualPropertyTaxesFromSellerTaxCredit — the back-solve behind the pencil", () => {
  it("round-trips the fixture's credit to its annual taxes, to the cent", () => {
    const closingDay = parseIsoDate("2026-01-10")!;
    const creditOnTheFixture = sellerTaxCredit(3600, closingDay, false); // 88.77
    expect(annualPropertyTaxesFromSellerTaxCredit(creditOnTheFixture, closingDay, false)).toBeCloseTo(3600, 2);
    expect(annualPropertyTaxesFromSellerTaxCredit(177.53, closingDay, false)).toBeCloseTo(7199.83, 2); // 177.53 × 365 ÷ 9
  });

  it("reads a December reimbursement whatever sign it is typed with", () => {
    const decemberClosing = parseIsoDate("2026-12-15")!;
    const reimbursement = sellerTaxCredit(3600, decemberClosing, true); // −167.67, 17 days
    expect(reimbursement).toBeLessThan(0);
    expect(annualPropertyTaxesFromSellerTaxCredit(reimbursement, decemberClosing, true)).toBeCloseTo(3600, 2);
    expect(annualPropertyTaxesFromSellerTaxCredit(-reimbursement, decemberClosing, true)).toBeCloseTo(3600, 2);
  });

  it("prorates the inverse on the leap year's 366 days", () => {
    const leapDay = parseIsoDate("2024-02-29")!;
    expect(annualPropertyTaxesFromSellerTaxCredit((3650 * 59) / 366, leapDay, false)).toBeCloseTo(3650, 2);
  });

  it("has nothing to solve on a Jan 1 closing with unpaid taxes", () => {
    expect(sellerTaxCreditProratedDays(parseIsoDate("2026-01-01")!, false)).toBe(0);
    expect(annualPropertyTaxesFromSellerTaxCredit(100, parseIsoDate("2026-01-01")!, false)).toBeNull();
    expect(annualPropertyTaxesFromSellerTaxCredit(Number.NaN, parseIsoDate("2026-07-01")!, false)).toBeNull();
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
});

describe("Florida title & escrow estimate (mirror of the backend's title_escrow_buy_itemized_default)", () => {
  it("is exactly $1,540 on a $100k purchase with a $123k hard-money loan when we pay all closing costs", () => {
    const itemized = titleEscrowBuyItemizedDefault("we_pay_all", 100_000, 123_000);
    expect(itemized.titleOfficeAndSearchFees).toBe(600);
    expect(itemized.ownersTitlePolicyPremium).toBeCloseTo(575, 10);
    expect(itemized.lendersTitlePolicyAndEndorsements).toBeCloseTo(365, 10);
    expect(itemized.total).toBeCloseTo(1540, 10);
  });
  it("leaves the owner's policy to the seller on a standard deal: $965", () => {
    expect(titleEscrowBuyDefault("standard", 100_000, 123_000)).toBeCloseTo(965, 10);
    expect(titleEscrowBuyItemizedDefault("standard", 100_000, 123_000).ownersTitlePolicyPremium).toBe(0);
  });
  it.each([[80_000, 460], [100_000, 575], [250_000, 1325]])("owner's policy on a $%s price is $%s", (price, premium) => {
    expect(floridaOwnersTitlePolicyPremium(price)).toBeCloseTo(premium, 10);
  });
  it.each([72_000, 100_000])("the lender's policy is $250 flat when the $%s loan does not exceed the price", (loanAmount) => {
    expect(lendersTitlePolicyAndEndorsements(loanAmount, 100_000)).toBe(250);
  });
  it("paying all closing costs adds the owner's policy and the deed transfer tax", () => {
    expect(wePayAllExtraClosingCost(100_000)).toBeCloseTo(575 + 700, 10);
  });
});

describe("this year's tax bill paid by us at the purchase closing (mirror of the backend)", () => {
  const novemberClosing = { contractDate: "2026-11-10", buyClosingDate: "2026-11-20", annual_property_taxes: 3600 };

  it("is a closing line with the 4% November discount; the seller still credits their days and nothing is set aside", () => {
    const paidAtClosing = brrrAutoCalc({ ...FIXTURE, ...novemberClosing, buyerPaysCurrentYearTaxBillAtPurchaseClosing: true });
    const sellerPaid = brrrAutoCalc({ ...FIXTURE, ...novemberClosing, sellerPaidCurrentYearTaxes: true });
    expectCloseToTheCent(paidAtClosing.propertyTaxBillPaidAtPurchaseClosing, 3456);
    expect(paidAtClosing.sellerPaidCurrentYearTaxesEffective).toBe(false);
    expectCloseToTheCent(paidAtClosing.sellerTaxCredit, (3600 * 323) / 365);
    expectCloseToTheCent(paidAtClosing.closingCostsBuyTotal, sellerPaid.closingCostsBuyTotal! + 3456);
    // The bill is settled: same bucket timing as a seller-paid bill, and exactly the 4% discount cheaper at closing.
    expect(paidAtClosing.propertyTaxBucketDepositCountUntilFirstPayment).toBe(sellerPaid.propertyTaxBucketDepositCountUntilFirstPayment);
    expectCloseToTheCent(paidAtClosing.cashToCloseBuy! - sellerPaid.cashToCloseBuy!, -144);
  });

  it("takes the full bill before November and 3% off in December", () => {
    expect(currentYearPropertyTaxBillPaidAtPurchaseClosing(3600, parseIsoDate("2026-07-01")!)).toBe(3600);
    expectCloseToTheCent(currentYearPropertyTaxBillPaidAtPurchaseClosing(3600, parseIsoDate("2026-12-10")!), 3492);
    expect(brrrAutoCalc({ ...FIXTURE, ...novemberClosing }).propertyTaxBillPaidAtPurchaseClosing).toBe(0);
  });
});
