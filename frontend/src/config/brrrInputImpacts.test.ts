import { describe, expect, it } from "vitest";
import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";

import { BRRR_INPUT_IMPACTS, BRRR_OUTPUT_LABELS, impactText } from "./brrrInputImpacts";
import type { BrrrAnalyzeRes } from "../types";

/** Every input the BRRRR sections render, read off their `impactText('…')` calls. */
function renderedInputs(): string[] {
  const dir = join(__dirname, "..", "components", "deal", "brrr");
  const inputKeys = new Set<string>();
  for (const file of readdirSync(dir)) {
    const source = readFileSync(join(dir, file), "utf8");
    for (const match of source.matchAll(/impactText\('([A-Za-z_]+)'\)/g)) inputKeys.add(match[1]!);
  }
  return [...inputKeys];
}

const RESULT_KEYS: Array<keyof BrrrAnalyzeRes> = [
  "cash_flow", "dscr", "cash_out", "cash_out_routi", "cash_out_routi_conservative", "cash_to_refi_table_conservative",
  "cash_on_cash", "roi", "equity", "net_profit", "total_cash_needed_for_deal",
  "total_cash_invested", "cash_to_close_buy", "purchase_loan_amount", "hml_amount", "hml_payoff", "total_hard_money_cost",
  "prepaid_interest_buy", "seller_tax_credit", "closing_costs_buy_total", "stolen_money", "pre_refi_rental_income",
  "closing_costs_refi_total", "prepaid_interest_refi", "reserves_total",
];

describe("brrrInputImpacts", () => {
  it("covers every input the lifecycle sections render", () => {
    const rendered = renderedInputs();
    expect(rendered.length).toBeGreaterThan(40);
    const missing = rendered.filter((inputKey) => !(inputKey in BRRR_INPUT_IMPACTS));
    expect(missing).toEqual([]);
  });

  it("names only real outputs, each with a label", () => {
    for (const [input, outputs] of Object.entries(BRRR_INPUT_IMPACTS)) {
      expect(outputs.length, input).toBeGreaterThan(0);
      for (const key of outputs) {
        expect(RESULT_KEYS, `${input} -> ${key}`).toContain(key);
        expect(BRRR_OUTPUT_LABELS[key], key).toBeTruthy();
      }
    }
  });

  it("renders the tooltip text", () => {
    expect(impactText("earnestMoneyDeposit")).toBe("Affects: Cash to Close (Buy)");
    expect(impactText("rehabCushion")).toContain("Cash Needed");
    expect(impactText("nope")).toBe("");
  });
});
