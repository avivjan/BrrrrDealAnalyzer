/**
 * How a calculation step's number reads on screen, by the `unit` the backend's
 * explain layer stamps on every `CalcStep` (mirrors `_money` / `_pct` / `_ratio`
 * in `BackEnd/BL/reports/common/deal_pdf.py`, the PDF's renderer of the same data):
 *
 * - `money`  → `$1,234` when whole, `$1,234.56` otherwise, `-$1,234` when negative
 * - `pct`    → `12.50%`; the calculators encode ±∞ on percentage steps as -1 / -2
 * - `ratio`  → `1.20x`
 *
 * A step without a unit is money, which is the backend's default too. Money is
 * never decoded for the sentinels: -$1 and -$2 are real amounts.
 */
import type { CalcStep } from "../../types";

export type CalculationStepUnit = NonNullable<CalcStep["unit"]>;

const wholeDollars = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 0,
});

const centsDollars = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

export function formatCalculationStepMoney(value: number): string {
  return Number.isInteger(value) ? wholeDollars.format(value) : centsDollars.format(value);
}

export function formatCalculationStepPercent(value: number): string {
  if (value === -1) return "∞%";
  if (value === -2) return "-∞%";
  return `${value.toFixed(2)}%`;
}

export function formatCalculationStepRatio(value: number): string {
  return `${value.toFixed(2)}x`;
}

export function formatCalculationStepValueByUnit(
  unit: CalcStep["unit"],
  value: number,
): string {
  switch (unit) {
    case "pct":
      return formatCalculationStepPercent(value);
    case "ratio":
      return formatCalculationStepRatio(value);
    default:
      return formatCalculationStepMoney(value);
  }
}
