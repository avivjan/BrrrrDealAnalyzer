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
  const d = new Date(`${value}T00:00:00Z`);
  return Number.isNaN(d.getTime()) || d.toISOString().slice(0, 10) !== value ? null : d;
}

export function toIsoDate(d: Date): string {
  return d.toISOString().slice(0, 10);
}

export function addDays(iso: string, days: number): string | null {
  const d = parseIsoDate(iso);
  if (!d || !Number.isFinite(days)) return null;
  return toIsoDate(new Date(d.getTime() + Math.round(days) * MS_PER_DAY));
}

/** Whole days from `fromIso` to `toIso` (negative when `toIso` is earlier). */
export function daysBetween(fromIso: string, toIso: string): number | null {
  const a = parseIsoDate(fromIso);
  const b = parseIsoDate(toIso);
  if (!a || !b) return null;
  return Math.round((b.getTime() - a.getTime()) / MS_PER_DAY);
}

export function daysInMonth(d: Date): number {
  return new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth() + 1, 0)).getUTCDate();
}

export function daysInYear(d: Date): number {
  const y = d.getUTCFullYear();
  return (y % 4 === 0 && y % 100 !== 0) || y % 400 === 0 ? 366 : 365;
}

/** 1-based day of the year. */
export function dayOfYear(d: Date): number {
  return Math.round((d.getTime() - Date.UTC(d.getUTCFullYear(), 0, 1)) / MS_PER_DAY) + 1;
}

/** Days from `d` through the last day of its month, both inclusive (the prepaid window). */
export function daysThroughMonthEnd(d: Date): number {
  return daysInMonth(d) - d.getUTCDate() + 1;
}

export function recordingTransferDefault(loan: number): number {
  return RECORDING_RATE * loan + RECORDING_FLAT;
}

export function titleEscrowBuyDefault(mode: string | undefined, price: number): number {
  if (mode !== "we_pay_all") return TITLE_BUY_STANDARD;
  if (price < 150_000) return 2050;
  if (price <= 200_000) return 2200;
  return 2400;
}

export function titleEscrowRefiDefault(loan: number): number {
  return TITLE_REFI_FLAT + TITLE_REFI_RATE * loan;
}

/**
 * Property-tax proration, positive = the seller credits the buyer. Taxes are billed in
 * November: until paid, the seller owes Jan 1 → the day before closing; once paid (December
 * by default) the buyer owes closing → Dec 31.
 */
export function sellerTaxCredit(annualTaxes: number, closing: Date, sellerPaid: boolean): number {
  const yearDays = daysInYear(closing);
  const doy = dayOfYear(closing);
  return sellerPaid ? (-annualTaxes * (yearDays - doy + 1)) / yearDays : (annualTaxes * (doy - 1)) / yearDays;
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

const n = (v: unknown): number | null => toNumber(v) ?? null;
const nz = (v: unknown): number => toNumber(v) ?? 0;
const positive = (v: number | null): v is number => v != null && v > 0;

/** Every inline figure of the BRRRR form for the deal as typed so far. */
export function brrrAutoCalc(deal: DealInputModel): BrrrAutoCalc {
  const price = n(deal.purchasePrice);
  const priceDollars = positive(price) ? price * 1000 : null;
  const down = n(deal.down_payment);
  const arv = n(deal.arv_in_thousands);
  const arvDollars = positive(arv) ? arv * 1000 : null;
  const ltv = n(deal.ltv_as_precent);
  const rent = n(deal.rent);
  const hmlRate = n(deal.HMLInterestRate);
  const hmlPoints = n(deal.hmlPoints);
  const daysUntilRefi = n(deal.daysUntilRefi);
  const daysUntilRented = n(deal.daysUntilRented);
  const buy = parseIsoDate(deal.buyClosingDate ?? null);

  // -- Buy: the hard-money stack --------------------------------------------
  const purchaseLoanAmount = priceDollars != null && down != null ? priceDollars * (1 - down / 100) : null;
  const downPaymentCash = priceDollars != null && down != null ? (down / 100) * priceDollars : null;
  const rehabCostWithContingency = deal.rehabCost != null ? nz(deal.rehabCost) * 1000 * (1 + nz(deal.rehabContingency) / 100) : null;
  const constructionBudget = deal.constructionLoanBudget != null ? nz(deal.constructionLoanBudget) * 1000 : null;
  const hmlAmount = purchaseLoanAmount != null ? purchaseLoanAmount + (constructionBudget ?? 0) : null;
  const hmlPointsDollars = hmlAmount != null && hmlPoints != null ? (hmlPoints / 100) * hmlAmount : null;
  const hmlPerDiem = hmlAmount != null && hmlRate != null ? (hmlAmount * hmlRate) / HML_DAYS_PER_YEAR / 100 : null;
  const hmlInterestTotal = hmlPerDiem != null && daysUntilRefi != null ? hmlPerDiem * daysUntilRefi : null;

  // -- Timeline ----------------------------------------------------------------
  const refiClosingDate = buy && daysUntilRefi != null ? addDays(deal.buyClosingDate!, daysUntilRefi) : null;
  const tenantOccupiedDate = buy && daysUntilRented != null ? addDays(deal.buyClosingDate!, daysUntilRented) : null;
  const prepaidDaysBuy = buy && daysUntilRefi != null ? Math.min(daysThroughMonthEnd(buy), daysUntilRefi) : null;
  const refi = refiClosingDate ? parseIsoDate(refiClosingDate) : null;
  const prepaidDaysRefi = refi ? daysThroughMonthEnd(refi) : null;
  const sameMonth = !!buy && !!refi && buy.getUTCFullYear() === refi.getUTCFullYear() && buy.getUTCMonth() === refi.getUTCMonth();
  const accruedDays = refi ? (sameMonth ? 0 : refi.getUTCDate() - 1) : 0;

  const prepaidInterestBuy = hmlPerDiem != null && prepaidDaysBuy != null ? hmlPerDiem * prepaidDaysBuy : null;
  const accruedInterestAtPayoff = hmlPerDiem != null ? hmlPerDiem * accruedDays : 0;

  // -- Buy: the settlement -----------------------------------------------------
  const taxes = n(deal.annual_property_taxes);
  const sellerPaidEffective = buy ? (deal.sellerPaidCurrentYearTaxes ?? buy.getUTCMonth() === 11) : null;
  const taxCredit = buy && positive(taxes) ? sellerTaxCredit(taxes, buy, sellerPaidEffective as boolean) : buy ? 0 : null;
  const recordingBuyDefault = purchaseLoanAmount != null ? recordingTransferDefault(purchaseLoanAmount) : null;
  const titleBuyDefault = priceDollars != null ? titleEscrowBuyDefault(deal.titleModeBuy, priceDollars) : null;
  const recordingBuyEffective = deal.recordingTransferBuy != null ? nz(deal.recordingTransferBuy) : recordingBuyDefault;
  const titleBuyEffective = deal.titleEscrowBuy != null ? nz(deal.titleEscrowBuy) : titleBuyDefault;
  const notaryBuy = deal.onlineNotaryBuy === false ? 0 : NOTARY_FEE;
  const closingCostsBuyTotal =
    recordingBuyEffective != null && titleBuyEffective != null
      ? nz(deal.loanChargesBuy) + recordingBuyEffective + titleBuyEffective + notaryBuy + nz(deal.otherClosingCostsBuy)
      : null;
  const cashToCloseBuy =
    downPaymentCash != null && closingCostsBuyTotal != null
      ? downPaymentCash + closingCostsBuyTotal + (hmlPointsDollars ?? 0) + (prepaidInterestBuy ?? 0) - (taxCredit ?? 0) - nz(deal.earnestMoneyDeposit)
      : null;
  const totalHardMoneyCost =
    hmlPointsDollars != null && hmlInterestTotal != null ? hmlPointsDollars + hmlInterestTotal + nz(deal.loanChargesBuy) : null;

  // -- Rehab -------------------------------------------------------------------
  const stolenMoney = constructionBudget != null && rehabCostWithContingency != null ? constructionBudget - rehabCostWithContingency : null;

  // -- Rent & holding -----------------------------------------------------------
  const daysRentedBeforeRefi = daysUntilRefi != null && daysUntilRented != null ? Math.max(0, daysUntilRefi - daysUntilRented) : null;
  const preRefiRentalIncome = positive(rent) && daysRentedBeforeRefi != null ? (rent * daysRentedBeforeRefi) / DAYS_PER_MONTH : null;
  const utilitiesUntilRented = daysUntilRented != null ? (nz(deal.monthlyUtilitiesUntilRented) * daysUntilRented) / DAYS_PER_MONTH : null;

  // -- Refinance -----------------------------------------------------------------
  const refiLoanAmount = arvDollars != null && ltv != null ? arvDollars * (ltv / 100) : null;
  const lowestArvDefault = arvDollars != null ? LOWEST_ARV_FACTOR * arvDollars : null;
  const lowestArvEffective = deal.lowestArv != null ? nz(deal.lowestArv) * 1000 : lowestArvDefault;
  const conservativeRefiLoanAmount = lowestArvEffective != null && ltv != null ? lowestArvEffective * (ltv / 100) : null;
  const rate = n(deal.interestRate);
  const lines = (loan: number | null) => {
    if (loan == null) return { broker: null, recording: null, title: null, total: null, prepaid: null };
    const broker = (nz(deal.refiPoints) / 100) * loan;
    const recording = deal.recordingTransferRefi != null ? nz(deal.recordingTransferRefi) : recordingTransferDefault(loan);
    const title = deal.titleEscrowRefi != null ? nz(deal.titleEscrowRefi) : titleEscrowRefiDefault(loan);
    const notary = deal.onlineNotaryRefi === false ? 0 : NOTARY_FEE;
    const total =
      nz(deal.loanChargesRefi) + recording + title + notary + nz(deal.appraisalFee) + nz(deal.surveyFee) +
      nz(deal.refiUnderwritingFee) + broker + nz(deal.brokerProcessingFeeRefi) + nz(deal.otherClosingCostsRefi);
    const prepaid = rate != null && prepaidDaysRefi != null ? (loan * rate * prepaidDaysRefi) / DSCR_DAYS_PER_YEAR / 100 : null;
    return { broker, recording, title, total, prepaid };
  };
  const base = lines(refiLoanAmount);
  const cons = lines(conservativeRefiLoanAmount);
  const vacancyReserveDefault = rent;
  const vacancyReserveEffective = deal.vacancyReserve != null ? nz(deal.vacancyReserve) : vacancyReserveDefault;
  const reservesTotal = vacancyReserveEffective != null ? nz(deal.maintenanceReserve) + vacancyReserveEffective + nz(deal.capexReserve) : null;
  const hmlPayoff = hmlAmount != null ? hmlAmount + accruedInterestAtPayoff : null;
  const wire = (loan: number | null, l: ReturnType<typeof lines>) =>
    loan != null && hmlPayoff != null && l.total != null && reservesTotal != null ? loan - hmlPayoff - l.total - (l.prepaid ?? 0) - reservesTotal : null;

  return {
    purchaseLoanAmount, downPaymentCash, hmlAmount, hmlPointsDollars, hmlPerDiem, hmlInterestTotal,
    prepaidDaysBuy, prepaidInterestBuy, sellerPaidCurrentYearTaxesEffective: sellerPaidEffective, sellerTaxCredit: taxCredit,
    recordingTransferBuyDefault: recordingBuyDefault, titleEscrowBuyDefault: titleBuyDefault,
    recordingTransferBuyEffective: recordingBuyEffective, titleEscrowBuyEffective: titleBuyEffective,
    notaryBuy, closingCostsBuyTotal, cashToCloseBuy, totalHardMoneyCost,
    rehabCostWithContingency, constructionBudget, stolenMoney,
    tenantOccupiedDate, daysRentedBeforeRefi, preRefiRentalIncome, utilitiesUntilRented,
    refiClosingDate, refiLoanAmount, lowestArvDefault, lowestArvEffective, conservativeRefiLoanAmount,
    brokerPointsDollars: base.broker, recordingTransferRefiDefault: refiLoanAmount != null ? recordingTransferDefault(refiLoanAmount) : null,
    titleEscrowRefiDefault: refiLoanAmount != null ? titleEscrowRefiDefault(refiLoanAmount) : null,
    recordingTransferRefiEffective: base.recording, titleEscrowRefiEffective: base.title,
    notaryRefi: deal.onlineNotaryRefi === false ? 0 : NOTARY_FEE, closingCostsRefiTotal: base.total,
    prepaidDaysRefi, prepaidInterestRefi: base.prepaid,
    vacancyReserveDefault, vacancyReserveEffective, reservesTotal, hmlPayoff,
    cashOutWire: wire(refiLoanAmount, base), cashOutWireConservative: wire(conservativeRefiLoanAmount, cons),
  };
}
