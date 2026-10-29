/**
 * The inline figures the BRRRR form shows next to its inputs, computed client-side.
 *
 * A mirror of the backend engine (`BackEnd/BL/analyze/brrrSteps/`) for the handful of
 * values a reader wants instantly while typing — loan amounts, per diems, the prepaid
 * windows, the seller tax credit, the settlement totals, the draw spread, the wires.
 * The Analyze page never calls the API before save and the modals debounce it, so these
 * cannot wait for a response. The backend stays the source of truth: the saved-deal views
 * prefer the server's `*_effective` values, and `brrrAutoCalc.test.ts` pins these formulas
 * to the backend fixture's numbers.
 *
 * Every figure is `null` until the inputs it needs are present ("appears only when it has
 * all the required fields"). Money in dollars; the thousands fields are scaled here.
 */
import type { DealInputModel } from "../types";
import { toNumber } from "./dealUtils";

export const NOTARY_FEE = 250;
export const RECORDING_RATE = 0.0055;
export const RECORDING_FLAT = 250;
export const TITLE_BUY_STANDARD = 1000;
export const TITLE_REFI_FLAT = 800;
export const TITLE_REFI_RATE = 0.0045;
export const DEED_TRANSFER_TAX_RATE_WE_PAY_ALL = 0.007;
export const LOWEST_ARV_FACTOR = 0.9;
export const HML_DAYS_PER_YEAR = 360;
/** The refi settlement statements quote the DSCR loan's per diem on a 360-day year too. */
export const DSCR_DAYS_PER_YEAR = 360;
export const DAYS_PER_MONTH = 30;
/** Property taxes are paid on Nov 30 with the 4% November discount. */
export const PROPERTY_TAX_NOVEMBER_PAYMENT_FACTOR = 0.96;
export const PROPERTY_TAX_BUCKET_DEPOSIT_DAY_OF_MONTH = 15;
export const HYSA_DEPOSIT_MONTHS_OF_PRINCIPAL_AND_INTEREST = 3;

const MS_PER_DAY = 86_400_000;

/** `YYYY-MM-DD` → UTC-midnight Date, or null when not a valid ISO calendar date. */
export function parseIsoDate(value: string | null | undefined): Date | null {
  if (!value || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return null;
  const parsedDate = new Date(`${value}T00:00:00Z`);
  return Number.isNaN(parsedDate.getTime()) || parsedDate.toISOString().slice(0, 10) !== value ? null : parsedDate;
}

export function toIsoDate(day: Date): string {
  return day.toISOString().slice(0, 10);
}

export function addDays(isoDate: string, days: number): string | null {
  const day = parseIsoDate(isoDate);
  if (!day || !Number.isFinite(days)) return null;
  return toIsoDate(new Date(day.getTime() + Math.round(days) * MS_PER_DAY));
}

/** Whole days from `fromIsoDate` to `toIsoDate` (negative when `toIsoDate` is earlier). */
export function daysBetween(fromIsoDate: string, toIsoDate: string): number | null {
  const fromDay = parseIsoDate(fromIsoDate);
  const toDay = parseIsoDate(toIsoDate);
  if (!fromDay || !toDay) return null;
  return Math.round((toDay.getTime() - fromDay.getTime()) / MS_PER_DAY);
}

export function daysInMonth(day: Date): number {
  return new Date(Date.UTC(day.getUTCFullYear(), day.getUTCMonth() + 1, 0)).getUTCDate();
}

export function daysInYear(day: Date): number {
  const year = day.getUTCFullYear();
  return (year % 4 === 0 && year % 100 !== 0) || year % 400 === 0 ? 366 : 365;
}

/** 1-based day of the year. */
export function dayOfYear(day: Date): number {
  return Math.round((day.getTime() - Date.UTC(day.getUTCFullYear(), 0, 1)) / MS_PER_DAY) + 1;
}

/** Days from `day` through the last day of its month, both inclusive (the prepaid window). */
export function daysThroughMonthEnd(day: Date): number {
  return daysInMonth(day) - day.getUTCDate() + 1;
}

/** Every 15th of a month strictly after `afterDay` and on or before `throughDay`. */
export function propertyTaxBucketDepositDates(afterDay: Date, throughDay: Date): Date[] {
  const depositDates: Date[] = [];
  let year = afterDay.getUTCFullYear();
  let month = afterDay.getUTCMonth();
  for (;;) {
    const depositDate = new Date(Date.UTC(year, month, PROPERTY_TAX_BUCKET_DEPOSIT_DAY_OF_MONTH));
    if (depositDate.getTime() > throughDay.getTime()) return depositDates;
    if (depositDate.getTime() > afterDay.getTime()) depositDates.push(depositDate);
    [year, month] = month === 11 ? [year + 1, 0] : [year, month + 1];
  }
}

/** The first Nov 30 the owner pays: this year's, or next year's after a December closing. */
export function firstPropertyTaxPaymentDate(buyClosingDay: Date): Date {
  const thisYearsPaymentDate = new Date(Date.UTC(buyClosingDay.getUTCFullYear(), 10, 30));
  return buyClosingDay.getTime() <= thisYearsPaymentDate.getTime() ? thisYearsPaymentDate : new Date(Date.UTC(buyClosingDay.getUTCFullYear() + 1, 10, 30));
}

/** Monthly principal and interest of the DSCR loan (straight-line at 0%), as the backend's `calc_mortgage_payment`. */
export function monthlyPrincipalAndInterest(loanAmount: number, annualInterestRatePercent: number, loanTermYears: number): number | null {
  const totalPayments = loanTermYears * 12;
  if (!(totalPayments > 0)) return null;
  const monthlyInterestRate = annualInterestRatePercent / 100 / 12;
  if (monthlyInterestRate === 0) return loanAmount / totalPayments;
  const factor = (1 + monthlyInterestRate) ** totalPayments;
  return (loanAmount * monthlyInterestRate * factor) / (factor - 1);
}

/** Refi: 0.55% of the loan recorded + $250. */
export function recordingTransferDefault(loanAmount: number): number {
  return RECORDING_RATE * loanAmount + RECORDING_FLAT;
}

/** Deed transfer tax at purchase: the seller's debit on a standard deal, 0.70% of the price when we pay all closing costs. */
export function deedTransferTaxBuyDefault(titleMode: string | undefined, purchasePriceDollars: number): number {
  return titleMode === "we_pay_all" ? DEED_TRANSFER_TAX_RATE_WE_PAY_ALL * purchasePriceDollars : 0;
}

/** Buy: $250 + 0.55% of the WHOLE hard-money loan (purchase loan + construction budget) + the deed transfer tax. */
export function recordingTransferBuyDefault(hmlAmount: number, deedTransferTax: number): number {
  return RECORDING_FLAT + RECORDING_RATE * hmlAmount + deedTransferTax;
}

/** What paying all closing costs adds over a standard deal: the title tier step-up plus the deed transfer tax. */
export function wePayAllExtraClosingCost(purchasePriceDollars: number): number {
  return titleEscrowBuyDefault("we_pay_all", purchasePriceDollars) - TITLE_BUY_STANDARD + deedTransferTaxBuyDefault("we_pay_all", purchasePriceDollars);
}

export function titleEscrowBuyDefault(titleMode: string | undefined, purchasePriceDollars: number): number {
  if (titleMode !== "we_pay_all") return TITLE_BUY_STANDARD;
  if (purchasePriceDollars < 150_000) return 2050;
  if (purchasePriceDollars <= 200_000) return 2200;
  return 2400;
}

export function titleEscrowRefiDefault(loanAmount: number): number {
  return TITLE_REFI_FLAT + TITLE_REFI_RATE * loanAmount;
}

/**
 * Property-tax proration, positive = the seller credits the buyer. Taxes are billed in
 * November: until paid, the seller owes Jan 1 → the day before closing; once paid (December
 * by default) the buyer owes closing → Dec 31.
 */
export function sellerTaxCredit(annualPropertyTaxes: number, closingDay: Date, sellerAlreadyPaidCurrentYearTaxes: boolean): number {
  const daysInClosingYear = daysInYear(closingDay);
  const closingDayOfYear = dayOfYear(closingDay);
  return sellerAlreadyPaidCurrentYearTaxes
    ? (-annualPropertyTaxes * (daysInClosingYear - closingDayOfYear + 1)) / daysInClosingYear
    : (annualPropertyTaxes * (closingDayOfYear - 1)) / daysInClosingYear;
}

/** The days the proration covers: the seller's (Jan 1 → the day before closing) or, once paid, the buyer's (closing → Dec 31). */
export function sellerTaxCreditProratedDays(closingDay: Date, sellerAlreadyPaidCurrentYearTaxes: boolean): number {
  const closingDayOfYear = dayOfYear(closingDay);
  return sellerAlreadyPaidCurrentYearTaxes ? daysInYear(closingDay) - closingDayOfYear + 1 : closingDayOfYear - 1;
}

/**
 * The inverse of `sellerTaxCredit`: the annual taxes that produce the credit actually received at
 * closing, so typing the settlement-statement credit back-solves Annual Taxes. Works on the
 * credit's absolute value (the seller-paid state supplies the sign), rounded to cents because
 * the field is stored at two decimals. `null` when the proration covers no days (a Jan 1
 * closing with unpaid taxes): every tax gives a $0 credit, so there is nothing to solve.
 */
export function annualPropertyTaxesFromSellerTaxCredit(sellerTaxCreditDollars: number, closingDay: Date, sellerAlreadyPaidCurrentYearTaxes: boolean): number | null {
  const proratedDays = sellerTaxCreditProratedDays(closingDay, sellerAlreadyPaidCurrentYearTaxes);
  if (proratedDays <= 0 || !Number.isFinite(sellerTaxCreditDollars)) return null;
  return Math.round(((Math.abs(sellerTaxCreditDollars) * daysInYear(closingDay)) / proratedDays) * 100) / 100;
}

export interface BrrrAutoCalc {
  // Buy
  purchaseLoanAmount: number | null;
  downPaymentCash: number | null;
  hmlAmount: number | null;
  hmlPointsDollars: number | null;
  hmlPerDiem: number | null;
  hmlInterestTotal: number | null;
  prepaidDaysBuy: number | null;
  prepaidInterestBuy: number | null;
  sellerPaidCurrentYearTaxesEffective: boolean | null;
  /** The proration by the closing date (what the "auto" credit is). */
  sellerTaxCreditFormula: number | null;
  /** Effective: the typed settlement-statement credit, or the formula. */
  sellerTaxCredit: number | null;
  insuranceBillAtPurchaseInsideClosing: number;
  /** Days the proration covers; 0 on a Jan 1 closing with unpaid taxes (nothing to back-solve). */
  sellerTaxCreditProratedDays: number | null;
  deedTransferTaxBuy: number | null;
  recordingTransferBuyDefault: number | null;
  titleEscrowBuyDefault: number | null;
  wePayAllExtraClosingCost: number | null;
  recordingTransferBuyEffective: number | null;
  titleEscrowBuyEffective: number | null;
  notaryBuy: number;
  closingCostsBuyTotal: number | null;
  cashToCloseBuy: number | null;
  totalHardMoneyCost: number | null;
  // Rehab
  rehabCostWithContingency: number | null;
  constructionBudget: number | null;
  stolenMoney: number | null;
  rehabCompletedDate: string | null;
  // Rent & holding
  tenantOccupiedDate: string | null;
  /** The bill × 0.96 paid on Nov 30. */
  propertyTaxBillPaidOnNovember30: number | null;
  firstPropertyTaxPaymentDate: string | null;
  /** The 15ths after closing through the first Nov 30 (1 when none is left); null without a closing date. */
  propertyTaxBucketDepositCountUntilFirstPayment: number | null;
  propertyTaxBucketDepositDefault: number | null;
  propertyTaxBucketDepositEffective: number | null;
  /** Deposits of the first bill made on or before the refi (days ÷ 30 without a closing date). */
  propertyTaxBucketFirstBillDepositCountUntilRefi: number | null;
  /** The regular-year tax after the refi: bill × 0.96 ÷ 12. */
  monthlyPropertyTaxAfterRefi: number | null;
  insurancePaidMonthlyUntilRefi: number | null;
  daysRentedBeforeRefi: number | null;
  preRefiRentalIncome: number | null;
  utilitiesUntilRented: number | null;
  // Refinance
  refiClosingDate: string | null;
  refiLoanAmount: number | null;
  lowestArvDefault: number | null;
  lowestArvEffective: number | null;
  conservativeRefiLoanAmount: number | null;
  brokerPointsDollars: number | null;
  recordingTransferRefiDefault: number | null;
  titleEscrowRefiDefault: number | null;
  recordingTransferRefiEffective: number | null;
  titleEscrowRefiEffective: number | null;
  notaryRefi: number;
  closingCostsRefiTotal: number | null;
  insuranceBillAtRefiDefault: number | null;
  insuranceBillAtRefiEffective: number | null;
  insuranceBillAtRefiInsideClosing: number;
  monthlyInsuranceAfterRefiDefault: number | null;
  propertyTaxLumpSumAtRefiClosingDefault: number | null;
  propertyTaxLumpSumAtRefiClosingEffective: number;
  appraisalAndSurveyPaidOutsideClosing: number;
  monthlyPrincipalAndInterest: number | null;
  hysaDepositAtRefiDefault: number | null;
  hysaDepositAtRefiEffective: number | null;
  prepaidDaysRefi: number | null;
  prepaidInterestRefi: number | null;
  vacancyReserveDefault: number | null;
  vacancyReserveEffective: number | null;
  reservesTotal: number | null;
  hmlPayoff: number | null;
  cashOutWire: number | null;
  cashOutWireConservative: number | null;
}

const numberOrNull = (value: unknown): number | null => toNumber(value) ?? null;
const numberOrZero = (value: unknown): number => toNumber(value) ?? 0;
const isPositive = (value: number | null): value is number => value != null && value > 0;

/** Every inline figure of the BRRRR form for the deal as typed so far. */
export function brrrAutoCalc(deal: DealInputModel): BrrrAutoCalc {
  const purchasePriceThousands = numberOrNull(deal.purchasePrice);
  const purchasePriceDollars = isPositive(purchasePriceThousands) ? purchasePriceThousands * 1000 : null;
  const downPaymentPercent = numberOrNull(deal.down_payment);
  const arvThousands = numberOrNull(deal.arv_in_thousands);
  const arvDollars = isPositive(arvThousands) ? arvThousands * 1000 : null;
  const ltvPercent = numberOrNull(deal.ltv_as_precent);
  const monthlyRent = numberOrNull(deal.rent);
  const hmlInterestRatePercent = numberOrNull(deal.HMLInterestRate);
  const hmlPointsPercent = numberOrNull(deal.hmlPoints);
  const daysUntilRefi = numberOrNull(deal.daysUntilRefi);
  const daysUntilRented = numberOrNull(deal.daysUntilRented);
  const buyClosingDay = parseIsoDate(deal.buyClosingDate ?? null);

  // -- Buy: the hard-money stack --------------------------------------------
  const purchaseLoanAmount = purchasePriceDollars != null && downPaymentPercent != null ? purchasePriceDollars * (1 - downPaymentPercent / 100) : null;
  const downPaymentCash = purchasePriceDollars != null && downPaymentPercent != null ? (downPaymentPercent / 100) * purchasePriceDollars : null;
  const rehabCostWithContingency = deal.rehabCost != null ? numberOrZero(deal.rehabCost) * 1000 * (1 + numberOrZero(deal.rehabContingency) / 100) : null;
  const constructionBudget = deal.constructionLoanBudget != null ? numberOrZero(deal.constructionLoanBudget) * 1000 : null;
  const hmlAmount = purchaseLoanAmount != null ? purchaseLoanAmount + (constructionBudget ?? 0) : null;
  const hmlPointsDollars = hmlAmount != null && hmlPointsPercent != null ? (hmlPointsPercent / 100) * hmlAmount : null;
  const hmlPerDiem = hmlAmount != null && hmlInterestRatePercent != null ? (hmlAmount * hmlInterestRatePercent) / HML_DAYS_PER_YEAR / 100 : null;
  const hmlInterestTotal = hmlPerDiem != null && daysUntilRefi != null ? hmlPerDiem * daysUntilRefi : null;

  // -- Timeline ----------------------------------------------------------------
  const refiClosingDate = buyClosingDay && daysUntilRefi != null ? addDays(deal.buyClosingDate!, daysUntilRefi) : null;
  const tenantOccupiedDate = buyClosingDay && daysUntilRented != null ? addDays(deal.buyClosingDate!, daysUntilRented) : null;
  const prepaidDaysBuy = buyClosingDay && daysUntilRefi != null ? Math.min(daysThroughMonthEnd(buyClosingDay), daysUntilRefi) : null;
  const refiClosingDay = refiClosingDate ? parseIsoDate(refiClosingDate) : null;
  const prepaidDaysRefi = refiClosingDay ? daysThroughMonthEnd(refiClosingDay) : null;
  const refiClosesInPurchaseMonth = !!buyClosingDay && !!refiClosingDay && buyClosingDay.getUTCFullYear() === refiClosingDay.getUTCFullYear() && buyClosingDay.getUTCMonth() === refiClosingDay.getUTCMonth();
  const hmlInterestDaysAccruedIntoRefiPayoff = refiClosingDay ? (refiClosesInPurchaseMonth ? 0 : refiClosingDay.getUTCDate() - 1) : 0;

  const prepaidInterestBuy = hmlPerDiem != null && prepaidDaysBuy != null ? hmlPerDiem * prepaidDaysBuy : null;
  const accruedInterestAtPayoff = hmlPerDiem != null ? hmlPerDiem * hmlInterestDaysAccruedIntoRefiPayoff : 0;

  // -- Buy: the settlement -----------------------------------------------------
  const annualPropertyTaxes = numberOrNull(deal.annual_property_taxes);
  const sellerAlreadyPaidCurrentYearTaxesEffective = buyClosingDay ? (deal.sellerPaidCurrentYearTaxes ?? buyClosingDay.getUTCMonth() === 11) : null;
  const sellerTaxCreditFormulaAmount = buyClosingDay && isPositive(annualPropertyTaxes) ? sellerTaxCredit(annualPropertyTaxes, buyClosingDay, sellerAlreadyPaidCurrentYearTaxesEffective as boolean) : buyClosingDay ? 0 : null;
  // The figure typed from the settlement statement wins over the proration.
  const sellerTaxCreditAmount = deal.sellerTaxCreditAtPurchaseClosing != null ? numberOrZero(deal.sellerTaxCreditAtPurchaseClosing) : sellerTaxCreditFormulaAmount;
  const insuranceBillAtPurchase = numberOrZero(deal.annual_insurance);
  const insuranceBillAtPurchaseInsideClosing = deal.insurancePurchaseBillPaymentTiming === "outside_purchase_closing" ? 0 : insuranceBillAtPurchase;
  const sellerTaxCreditProratedDaysCount = buyClosingDay ? sellerTaxCreditProratedDays(buyClosingDay, sellerAlreadyPaidCurrentYearTaxesEffective as boolean) : null;
  const deedTransferTaxBuy = purchasePriceDollars != null ? deedTransferTaxBuyDefault(deal.titleModeBuy, purchasePriceDollars) : null;
  const recordingTransferBuyDefaultAmount = hmlAmount != null && deedTransferTaxBuy != null ? recordingTransferBuyDefault(hmlAmount, deedTransferTaxBuy) : null;
  const wePayAllExtra = purchasePriceDollars != null ? wePayAllExtraClosingCost(purchasePriceDollars) : null;
  const titleEscrowBuyDefaultAmount = purchasePriceDollars != null ? titleEscrowBuyDefault(deal.titleModeBuy, purchasePriceDollars) : null;
  const recordingTransferBuyEffectiveAmount = deal.recordingTransferBuy != null ? numberOrZero(deal.recordingTransferBuy) : recordingTransferBuyDefaultAmount;
  const titleEscrowBuyEffectiveAmount = deal.titleEscrowBuy != null ? numberOrZero(deal.titleEscrowBuy) : titleEscrowBuyDefaultAmount;
  const notaryBuy = deal.onlineNotaryBuy === false ? 0 : (deal.onlineNotaryFeeBuy != null ? numberOrZero(deal.onlineNotaryFeeBuy) : NOTARY_FEE);
  const closingCostsBuyTotal =
    recordingTransferBuyEffectiveAmount != null && titleEscrowBuyEffectiveAmount != null
      ? numberOrZero(deal.loanChargesBuy) + recordingTransferBuyEffectiveAmount + titleEscrowBuyEffectiveAmount + notaryBuy + numberOrZero(deal.otherClosingCostsBuy)
        + insuranceBillAtPurchaseInsideClosing
      : null;
  const cashToCloseBuy =
    downPaymentCash != null && closingCostsBuyTotal != null
      ? downPaymentCash + closingCostsBuyTotal + (hmlPointsDollars ?? 0) + (prepaidInterestBuy ?? 0) - (sellerTaxCreditAmount ?? 0) - numberOrZero(deal.earnestMoneyDeposit)
      : null;
  const totalHardMoneyCost =
    hmlPointsDollars != null && hmlInterestTotal != null ? hmlPointsDollars + hmlInterestTotal + numberOrZero(deal.loanChargesBuy) : null;

  // -- Rehab -------------------------------------------------------------------
  const stolenMoney = constructionBudget != null && rehabCostWithContingency != null ? constructionBudget - rehabCostWithContingency : null;
  const daysUntilRehabCompleted = numberOrNull(deal.daysUntilRehabCompleted);
  const rehabCompletedDate = buyClosingDay && daysUntilRehabCompleted != null ? addDays(deal.buyClosingDate!, daysUntilRehabCompleted) : null;

  // -- The property's tax bucket until the refi ---------------------------------
  const propertyTaxBillPaidOnNovember30 = annualPropertyTaxes != null ? annualPropertyTaxes * PROPERTY_TAX_NOVEMBER_PAYMENT_FACTOR : null;
  const monthlyPropertyTaxAfterRefi = propertyTaxBillPaidOnNovember30 != null ? propertyTaxBillPaidOnNovember30 / 12 : null;
  const sellerTaxCreditSetAsideInTaxBucket = Math.max(0, sellerTaxCreditAmount ?? 0);
  const firstPaymentDay = buyClosingDay ? firstPropertyTaxPaymentDate(buyClosingDay) : null;
  const firstBillDepositDates = buyClosingDay && firstPaymentDay
    ? (propertyTaxBucketDepositDates(buyClosingDay, firstPaymentDay).length ? propertyTaxBucketDepositDates(buyClosingDay, firstPaymentDay) : [firstPaymentDay])
    : null;
  const propertyTaxBucketDepositCountUntilFirstPayment = firstBillDepositDates ? firstBillDepositDates.length : null;
  const propertyTaxBucketDepositDefault = propertyTaxBillPaidOnNovember30 == null ? null
    : propertyTaxBucketDepositCountUntilFirstPayment != null
      ? Math.max(0, (propertyTaxBillPaidOnNovember30 - sellerTaxCreditSetAsideInTaxBucket) / propertyTaxBucketDepositCountUntilFirstPayment)
      : monthlyPropertyTaxAfterRefi;
  const propertyTaxBucketDepositEffective = deal.monthlyPropertyTaxBucketDeposit != null ? numberOrZero(deal.monthlyPropertyTaxBucketDeposit) : propertyTaxBucketDepositDefault;
  const refiClosingDayForTaxes = refiClosingDate ? parseIsoDate(refiClosingDate) : null;
  const propertyTaxBucketFirstBillDepositCountUntilRefi = firstBillDepositDates
    ? (refiClosingDayForTaxes ? firstBillDepositDates.filter((depositDate) => depositDate.getTime() <= refiClosingDayForTaxes.getTime()).length : null)
    : daysUntilRefi != null ? daysUntilRefi / DAYS_PER_MONTH : null;
  const insurancePaidMonthlyUntilRefi = daysUntilRefi != null ? (numberOrZero(deal.monthlyInsuranceUntilRefi) * daysUntilRefi) / DAYS_PER_MONTH : null;

  // -- Rent & holding -----------------------------------------------------------
  const daysRentedBeforeRefi = daysUntilRefi != null && daysUntilRented != null ? Math.max(0, daysUntilRefi - daysUntilRented) : null;
  const preRefiRentalIncome = isPositive(monthlyRent) && daysRentedBeforeRefi != null ? (monthlyRent * daysRentedBeforeRefi) / DAYS_PER_MONTH : null;
  const utilitiesUntilRented = daysUntilRented != null ? (numberOrZero(deal.monthlyUtilitiesUntilRented) * daysUntilRented) / DAYS_PER_MONTH : null;

  // -- Refinance -----------------------------------------------------------------
  const refiLoanAmount = arvDollars != null && ltvPercent != null ? arvDollars * (ltvPercent / 100) : null;
  const lowestArvDefault = arvDollars != null ? LOWEST_ARV_FACTOR * arvDollars : null;
  // A typed lowest ARV that is not positive, or sits above a known ARV, is a wrong input
  // (`utils/dealInputValidation` says so on the field): nothing is computed from it.
  const lowestArvOverrideDollars = deal.lowestArv != null ? numberOrZero(deal.lowestArv) * 1000 : null;
  const lowestArvOverrideIsUsable = lowestArvOverrideDollars != null && lowestArvOverrideDollars > 0 && (arvDollars == null || lowestArvOverrideDollars <= arvDollars);
  const lowestArvEffective = deal.lowestArv != null ? (lowestArvOverrideIsUsable ? lowestArvOverrideDollars : null) : lowestArvDefault;
  const conservativeRefiLoanAmount = lowestArvEffective != null && ltvPercent != null ? lowestArvEffective * (ltvPercent / 100) : null;
  const refiInterestRatePercent = numberOrNull(deal.interestRate);
  const insuranceBillAtRefiDefault = insuranceBillAtPurchase;
  const insuranceBillAtRefiEffective = deal.insuranceBillAtRefiClosing != null ? numberOrZero(deal.insuranceBillAtRefiClosing) : insuranceBillAtRefiDefault;
  const insuranceBillAtRefiInsideClosing = deal.insuranceRefiBillPaymentTiming === "outside_refi_closing" ? 0 : insuranceBillAtRefiEffective;
  const monthlyInsuranceAfterRefiDefault = insuranceBillAtRefiEffective / 12;
  const propertyTaxLumpSumAtRefiClosingDefault = annualPropertyTaxes;
  const propertyTaxLumpSumAtRefiClosingEffective = deal.propertyTaxCollectionAtRefi === "full_tax_bill_collected_at_refi"
    ? (deal.propertyTaxLumpSumAtRefiClosing != null ? numberOrZero(deal.propertyTaxLumpSumAtRefiClosing) : numberOrZero(propertyTaxLumpSumAtRefiClosingDefault))
    : 0;
  // Paid outside the refi closing at the end of the rehab: not a settlement line.
  const appraisalAndSurveyPaidOutsideClosing = numberOrZero(deal.appraisalFee) + numberOrZero(deal.surveyFee);
  const refiSettlementLinesFor = (refiLoanAmount: number | null) => {
    if (refiLoanAmount == null) return { brokerPoints: null, recordingTransfer: null, titleEscrow: null, closingCostsTotal: null, prepaidInterest: null };
    const brokerPoints = (numberOrZero(deal.refiPoints) / 100) * refiLoanAmount;
    const recordingTransfer = deal.recordingTransferRefi != null ? numberOrZero(deal.recordingTransferRefi) : recordingTransferDefault(refiLoanAmount);
    const titleEscrow = deal.titleEscrowRefi != null ? numberOrZero(deal.titleEscrowRefi) : titleEscrowRefiDefault(refiLoanAmount);
    const notary = deal.onlineNotaryRefi === false ? 0 : (deal.onlineNotaryFeeRefi != null ? numberOrZero(deal.onlineNotaryFeeRefi) : NOTARY_FEE);
    const closingCostsTotal =
      numberOrZero(deal.loanChargesRefi) + recordingTransfer + titleEscrow + notary + numberOrZero(deal.refiUnderwritingFee) + brokerPoints +
      numberOrZero(deal.brokerProcessingFeeRefi) + numberOrZero(deal.otherClosingCostsRefi) + insuranceBillAtRefiInsideClosing + propertyTaxLumpSumAtRefiClosingEffective;
    const prepaidInterest =
      refiInterestRatePercent != null && prepaidDaysRefi != null ? (refiLoanAmount * refiInterestRatePercent * prepaidDaysRefi) / DSCR_DAYS_PER_YEAR / 100 : null;
    return { brokerPoints, recordingTransfer, titleEscrow, closingCostsTotal, prepaidInterest };
  };
  const settlementAtArv = refiSettlementLinesFor(refiLoanAmount);
  const settlementAtLowestArv = refiSettlementLinesFor(conservativeRefiLoanAmount);
  const vacancyReserveDefault = monthlyRent;
  const vacancyReserveEffective = deal.vacancyReserve != null ? numberOrZero(deal.vacancyReserve) : vacancyReserveDefault;
  const loanTermYears = numberOrNull(deal.loanTermYears);
  const principalAndInterest = refiLoanAmount != null && refiInterestRatePercent != null && loanTermYears != null
    ? monthlyPrincipalAndInterest(refiLoanAmount, refiInterestRatePercent, loanTermYears)
    : null;
  const hysaDepositAtRefiDefault = principalAndInterest != null ? HYSA_DEPOSIT_MONTHS_OF_PRINCIPAL_AND_INTEREST * principalAndInterest : null;
  const hysaDepositAtRefiEffective = deal.hysaDepositAtRefi != null ? numberOrZero(deal.hysaDepositAtRefi) : hysaDepositAtRefiDefault;
  // The owner's own money set aside after the wire: never taken off it.
  const reservesTotal = vacancyReserveEffective != null
    ? numberOrZero(deal.maintenanceReserve) + vacancyReserveEffective + numberOrZero(deal.capexReserve) + (hysaDepositAtRefiEffective ?? 0)
    : null;
  const hmlPayoff = hmlAmount != null ? hmlAmount + accruedInterestAtPayoff : null;
  const cashOutWireFor = (refiLoanAmount: number | null, settlementLines: ReturnType<typeof refiSettlementLinesFor>) =>
    refiLoanAmount != null && hmlPayoff != null && settlementLines.closingCostsTotal != null
      ? refiLoanAmount - hmlPayoff - settlementLines.closingCostsTotal - (settlementLines.prepaidInterest ?? 0)
      : null;

  return {
    purchaseLoanAmount, downPaymentCash, hmlAmount, hmlPointsDollars, hmlPerDiem, hmlInterestTotal,
    prepaidDaysBuy, prepaidInterestBuy, sellerPaidCurrentYearTaxesEffective: sellerAlreadyPaidCurrentYearTaxesEffective,
    sellerTaxCreditFormula: sellerTaxCreditFormulaAmount, sellerTaxCredit: sellerTaxCreditAmount, insuranceBillAtPurchaseInsideClosing,
    sellerTaxCreditProratedDays: sellerTaxCreditProratedDaysCount,
    deedTransferTaxBuy, recordingTransferBuyDefault: recordingTransferBuyDefaultAmount, titleEscrowBuyDefault: titleEscrowBuyDefaultAmount,
    wePayAllExtraClosingCost: wePayAllExtra,
    recordingTransferBuyEffective: recordingTransferBuyEffectiveAmount, titleEscrowBuyEffective: titleEscrowBuyEffectiveAmount,
    notaryBuy, closingCostsBuyTotal, cashToCloseBuy, totalHardMoneyCost,
    rehabCostWithContingency, constructionBudget, stolenMoney, rehabCompletedDate,
    tenantOccupiedDate, daysRentedBeforeRefi, preRefiRentalIncome, utilitiesUntilRented,
    propertyTaxBillPaidOnNovember30, firstPropertyTaxPaymentDate: firstPaymentDay ? toIsoDate(firstPaymentDay) : null,
    propertyTaxBucketDepositCountUntilFirstPayment, propertyTaxBucketDepositDefault, propertyTaxBucketDepositEffective,
    propertyTaxBucketFirstBillDepositCountUntilRefi, monthlyPropertyTaxAfterRefi, insurancePaidMonthlyUntilRefi,
    refiClosingDate, refiLoanAmount, lowestArvDefault, lowestArvEffective, conservativeRefiLoanAmount,
    brokerPointsDollars: settlementAtArv.brokerPoints, recordingTransferRefiDefault: refiLoanAmount != null ? recordingTransferDefault(refiLoanAmount) : null,
    titleEscrowRefiDefault: refiLoanAmount != null ? titleEscrowRefiDefault(refiLoanAmount) : null,
    recordingTransferRefiEffective: settlementAtArv.recordingTransfer, titleEscrowRefiEffective: settlementAtArv.titleEscrow,
    notaryRefi: deal.onlineNotaryRefi === false ? 0 : (deal.onlineNotaryFeeRefi != null ? numberOrZero(deal.onlineNotaryFeeRefi) : NOTARY_FEE), closingCostsRefiTotal: settlementAtArv.closingCostsTotal,
    insuranceBillAtRefiDefault, insuranceBillAtRefiEffective, insuranceBillAtRefiInsideClosing, monthlyInsuranceAfterRefiDefault,
    propertyTaxLumpSumAtRefiClosingDefault, propertyTaxLumpSumAtRefiClosingEffective, appraisalAndSurveyPaidOutsideClosing,
    monthlyPrincipalAndInterest: principalAndInterest, hysaDepositAtRefiDefault, hysaDepositAtRefiEffective,
    prepaidDaysRefi, prepaidInterestRefi: settlementAtArv.prepaidInterest,
    vacancyReserveDefault, vacancyReserveEffective, reservesTotal, hmlPayoff,
    cashOutWire: cashOutWireFor(refiLoanAmount, settlementAtArv), cashOutWireConservative: cashOutWireFor(conservativeRefiLoanAmount, settlementAtLowestArv),
  };
}
