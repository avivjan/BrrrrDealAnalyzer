/**
 * How each closing-cost estimate of the BRRRR form is calculated, in words and with the deal's
 * numbers: shown under its input while the field is on its formula default (`AutoDefaultMoneyInput`),
 * and worded like the breakdown popup's notes (`BackEnd/BL/analyze/explain/brrr.py`).
 *
 * Every function returns the lines to show, one idea per line, or `[]` while the numbers the
 * estimate needs are still missing.
 */
import { formatMoney } from "./money";
import {
  DEED_TRANSFER_TAX_RATE_WE_PAY_ALL,
  FLORIDA_OWNERS_POLICY_FIRST_TIER_UPPER_BOUND,
  RECORDING_FLAT,
  RECORDING_RATE,
  TITLE_REFI_FLAT,
  TITLE_REFI_RATE,
  type TitleEscrowBuyItemizedDefault,
} from "./brrrAutoCalc";

const formatPercent = (rate: number): string => `${(rate * 100).toFixed(2)}%`;

/** Title & Escrow / Settlement (Buy): the Florida estimate, line by line. */
export function titleEscrowBuyEstimateExplanationLines(itemized: TitleEscrowBuyItemizedDefault | null): string[] {
  if (itemized == null) return [];
  const officeFeesLine =
    `Office fees ${formatMoney(itemized.titleOfficeAndSearchFees)}: $350 settlement + $150 title search + $100 municipal lien search`;
  const ownersPolicyLine = !itemized.ownersTitlePolicyIsOurs
    ? "Owner's policy $0: the seller pays it on a standard deal"
    : itemized.purchasePrice <= FLORIDA_OWNERS_POLICY_FIRST_TIER_UPPER_BOUND
      ? `Owner's policy ${formatMoney(itemized.ownersTitlePolicyPremium)}: FL promulgated rate (F.A.C. 69O-186.003), `
        + `${formatMoney(itemized.purchasePrice)} ÷ $1,000 × $5.75`
      : `Owner's policy ${formatMoney(itemized.ownersTitlePolicyPremium)}: FL promulgated rate (F.A.C. 69O-186.003), `
        + `$575 on the first $100,000 + $5.00 per $1,000 above`;
  const loanAbovePrice = Math.max(0, itemized.loanAmountInsured - itemized.purchasePrice);
  const lendersPolicyLine = loanAbovePrice > 0
    ? `Lender's policy ${formatMoney(itemized.lendersTitlePolicyAndEndorsements)}: $250 endorsements (ALTA 8.1, Form 9, simultaneous issue) `
      + `+ $5.00 per $1,000 of the ${formatMoney(loanAbovePrice)} loan above the price`
    : `Lender's policy ${formatMoney(itemized.lendersTitlePolicyAndEndorsements)}: $250 endorsements (ALTA 8.1, Form 9, simultaneous issue); `
      + `the loan does not exceed the price`;
  return [officeFeesLine, ownersPolicyLine, lendersPolicyLine];
}

/** Recording & Transfer (Buy): $250 + 0.55% of the whole hard-money loan + the deed transfer tax. */
export function recordingTransferBuyEstimateExplanationLines(
  hmlAmount: number | null,
  deedTransferTaxBuy: number | null,
  recordingTransferBuyDefault: number | null,
): string[] {
  if (hmlAmount == null || deedTransferTaxBuy == null || recordingTransferBuyDefault == null) return [];
  return [
    `${formatMoney(RECORDING_FLAT)} + ${formatPercent(RECORDING_RATE)} × ${formatMoney(hmlAmount)} + ${formatMoney(deedTransferTaxBuy)} `
      + `= ${formatMoney(recordingTransferBuyDefault)}`,
    `$250 records the deed, the mortgage and the LLC affidavit; 0.55% (0.35% doc stamps on the note + 0.20% intangible tax) `
      + `is on the whole hard-money loan (purchase loan + construction budget)`,
    deedTransferTaxBuy > 0
      ? `+ the ${formatPercent(DEED_TRANSFER_TAX_RATE_WE_PAY_ALL)} deed transfer tax, because we pay all closing costs`
      : `No deed transfer tax: the seller pays it on a standard deal`,
  ];
}

/** Recording & Transfer (Refi): 0.55% of the refi loan + $250. */
export function recordingTransferRefiEstimateExplanationLines(refiLoanAmount: number | null, recordingTransferRefiDefault: number | null): string[] {
  if (refiLoanAmount == null || recordingTransferRefiDefault == null) return [];
  return [
    `${formatPercent(RECORDING_RATE)} × ${formatMoney(refiLoanAmount)} refi loan + ${formatMoney(RECORDING_FLAT)} = ${formatMoney(recordingTransferRefiDefault)}`,
    `0.55% = 0.35% doc stamps on the note + 0.20% intangible tax; $250 records the mortgage`,
  ];
}

/** Title & Escrow / Settlement (Refi): $800 + 0.45% of the refi loan. */
export function titleEscrowRefiEstimateExplanationLines(refiLoanAmount: number | null, titleEscrowRefiDefault: number | null): string[] {
  if (refiLoanAmount == null || titleEscrowRefiDefault == null) return [];
  return [
    `${formatMoney(TITLE_REFI_FLAT)} + ${formatPercent(TITLE_REFI_RATE)} × ${formatMoney(refiLoanAmount)} refi loan = ${formatMoney(titleEscrowRefiDefault)}`,
    `Settlement and search fees and the lender's title policy together`,
  ];
}
