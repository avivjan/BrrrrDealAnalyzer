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
export const LOWEST_ARV_FACTOR = 0.9;
export const HML_DAYS_PER_YEAR = 360;
export const DSCR_DAYS_PER_YEAR = 365;
export const DAYS_PER_MONTH = 30;

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

export function recordingTransferDefault(loanAmount: number): number {
  return RECORDING_RATE * loanAmount + RECORDING_FLAT;
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
  sellerTaxCredit: number | null;
  recordingTransferBuyDefault: number | null;
  titleEscrowBuyDefault: number | null;
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
  // Rent & holding
  tenantOccupiedDate: string | null;
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
  const sellerTaxCreditAmount = buyClosingDay && isPositive(annualPropertyTaxes) ? sellerTaxCredit(annualPropertyTaxes, buyClosingDay, sellerAlreadyPaidCurrentYearTaxesEffective as boolean) : buyClosingDay ? 0 : null;
  const recordingTransferBuyDefaultAmount = purchaseLoanAmount != null ? recordingTransferDefault(purchaseLoanAmount) : null;
  const titleEscrowBuyDefaultAmount = purchasePriceDollars != null ? titleEscrowBuyDefault(deal.titleModeBuy, purchasePriceDollars) : null;
  const recordingTransferBuyEffectiveAmount = deal.recordingTransferBuy != null ? numberOrZero(deal.recordingTransferBuy) : recordingTransferBuyDefaultAmount;
  const titleEscrowBuyEffectiveAmount = deal.titleEscrowBuy != null ? numberOrZero(deal.titleEscrowBuy) : titleEscrowBuyDefaultAmount;
  const notaryBuy = deal.onlineNotaryBuy === false ? 0 : NOTARY_FEE;
  const closingCostsBuyTotal =
    recordingTransferBuyEffectiveAmount != null && titleEscrowBuyEffectiveAmount != null
      ? numberOrZero(deal.loanChargesBuy) + recordingTransferBuyEffectiveAmount + titleEscrowBuyEffectiveAmount + notaryBuy + numberOrZero(deal.otherClosingCostsBuy)
      : null;
  const cashToCloseBuy =
    downPaymentCash != null && closingCostsBuyTotal != null
      ? downPaymentCash + closingCostsBuyTotal + (hmlPointsDollars ?? 0) + (prepaidInterestBuy ?? 0) - (sellerTaxCreditAmount ?? 0) - numberOrZero(deal.earnestMoneyDeposit)
      : null;
  const totalHardMoneyCost =
    hmlPointsDollars != null && hmlInterestTotal != null ? hmlPointsDollars + hmlInterestTotal + numberOrZero(deal.loanChargesBuy) : null;

  // -- Rehab -------------------------------------------------------------------
  const stolenMoney = constructionBudget != null && rehabCostWithContingency != null ? constructionBudget - rehabCostWithContingency : null;

  // -- Rent & holding -----------------------------------------------------------
  const daysRentedBeforeRefi = daysUntilRefi != null && daysUntilRented != null ? Math.max(0, daysUntilRefi - daysUntilRented) : null;
  const preRefiRentalIncome = isPositive(monthlyRent) && daysRentedBeforeRefi != null ? (monthlyRent * daysRentedBeforeRefi) / DAYS_PER_MONTH : null;
  const utilitiesUntilRented = daysUntilRented != null ? (numberOrZero(deal.monthlyUtilitiesUntilRented) * daysUntilRented) / DAYS_PER_MONTH : null;

  // -- Refinance -----------------------------------------------------------------
  const refiLoanAmount = arvDollars != null && ltvPercent != null ? arvDollars * (ltvPercent / 100) : null;
  const lowestArvDefault = arvDollars != null ? LOWEST_ARV_FACTOR * arvDollars : null;
  const lowestArvEffective = deal.lowestArv != null ? numberOrZero(deal.lowestArv) * 1000 : lowestArvDefault;
  const conservativeRefiLoanAmount = lowestArvEffective != null && ltvPercent != null ? lowestArvEffective * (ltvPercent / 100) : null;
  const refiInterestRatePercent = numberOrNull(deal.interestRate);
  const refiSettlementLinesFor = (refiLoanAmount: number | null) => {
    if (refiLoanAmount == null) return { brokerPoints: null, recordingTransfer: null, titleEscrow: null, closingCostsTotal: null, prepaidInterest: null };
    const brokerPoints = (numberOrZero(deal.refiPoints) / 100) * refiLoanAmount;
    const recordingTransfer = deal.recordingTransferRefi != null ? numberOrZero(deal.recordingTransferRefi) : recordingTransferDefault(refiLoanAmount);
    const titleEscrow = deal.titleEscrowRefi != null ? numberOrZero(deal.titleEscrowRefi) : titleEscrowRefiDefault(refiLoanAmount);
    const notary = deal.onlineNotaryRefi === false ? 0 : NOTARY_FEE;
    const closingCostsTotal =
      numberOrZero(deal.loanChargesRefi) + recordingTransfer + titleEscrow + notary + numberOrZero(deal.appraisalFee) + numberOrZero(deal.surveyFee) +
      numberOrZero(deal.refiUnderwritingFee) + brokerPoints + numberOrZero(deal.brokerProcessingFeeRefi) + numberOrZero(deal.otherClosingCostsRefi);
    const prepaidInterest =
      refiInterestRatePercent != null && prepaidDaysRefi != null ? (refiLoanAmount * refiInterestRatePercent * prepaidDaysRefi) / DSCR_DAYS_PER_YEAR / 100 : null;
    return { brokerPoints, recordingTransfer, titleEscrow, closingCostsTotal, prepaidInterest };
  };
  const settlementAtArv = refiSettlementLinesFor(refiLoanAmount);
  const settlementAtLowestArv = refiSettlementLinesFor(conservativeRefiLoanAmount);
  const vacancyReserveDefault = monthlyRent;
  const vacancyReserveEffective = deal.vacancyReserve != null ? numberOrZero(deal.vacancyReserve) : vacancyReserveDefault;
  const reservesTotal = vacancyReserveEffective != null ? numberOrZero(deal.maintenanceReserve) + vacancyReserveEffective + numberOrZero(deal.capexReserve) : null;
  const hmlPayoff = hmlAmount != null ? hmlAmount + accruedInterestAtPayoff : null;
  const cashOutWireFor = (refiLoanAmount: number | null, settlementLines: ReturnType<typeof refiSettlementLinesFor>) =>
    refiLoanAmount != null && hmlPayoff != null && settlementLines.closingCostsTotal != null && reservesTotal != null
      ? refiLoanAmount - hmlPayoff - settlementLines.closingCostsTotal - (settlementLines.prepaidInterest ?? 0) - reservesTotal
      : null;

  return {
    purchaseLoanAmount, downPaymentCash, hmlAmount, hmlPointsDollars, hmlPerDiem, hmlInterestTotal,
    prepaidDaysBuy, prepaidInterestBuy, sellerPaidCurrentYearTaxesEffective: sellerAlreadyPaidCurrentYearTaxesEffective, sellerTaxCredit: sellerTaxCreditAmount,
    recordingTransferBuyDefault: recordingTransferBuyDefaultAmount, titleEscrowBuyDefault: titleEscrowBuyDefaultAmount,
    recordingTransferBuyEffective: recordingTransferBuyEffectiveAmount, titleEscrowBuyEffective: titleEscrowBuyEffectiveAmount,
    notaryBuy, closingCostsBuyTotal, cashToCloseBuy, totalHardMoneyCost,
    rehabCostWithContingency, constructionBudget, stolenMoney,
    tenantOccupiedDate, daysRentedBeforeRefi, preRefiRentalIncome, utilitiesUntilRented,
    refiClosingDate, refiLoanAmount, lowestArvDefault, lowestArvEffective, conservativeRefiLoanAmount,
    brokerPointsDollars: settlementAtArv.brokerPoints, recordingTransferRefiDefault: refiLoanAmount != null ? recordingTransferDefault(refiLoanAmount) : null,
    titleEscrowRefiDefault: refiLoanAmount != null ? titleEscrowRefiDefault(refiLoanAmount) : null,
    recordingTransferRefiEffective: settlementAtArv.recordingTransfer, titleEscrowRefiEffective: settlementAtArv.titleEscrow,
    notaryRefi: deal.onlineNotaryRefi === false ? 0 : NOTARY_FEE, closingCostsRefiTotal: settlementAtArv.closingCostsTotal,
    prepaidDaysRefi, prepaidInterestRefi: settlementAtArv.prepaidInterest,
    vacancyReserveDefault, vacancyReserveEffective, reservesTotal, hmlPayoff,
    cashOutWire: cashOutWireFor(refiLoanAmount, settlementAtArv), cashOutWireConservative: cashOutWireFor(conservativeRefiLoanAmount, settlementAtLowestArv),
  };
}
