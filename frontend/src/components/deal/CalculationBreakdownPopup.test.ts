// @vitest-environment jsdom
import { afterEach, describe, expect, it } from "vitest";
import { mount, type VueWrapper } from "@vue/test-utils";
import { nextTick } from "vue";

import CalculationBreakdownPopup from "./CalculationBreakdownPopup.vue";
import type { CalcStep } from "../../types";

let wrapper: VueWrapper | null = null;

afterEach(() => {
  wrapper?.unmount();
  wrapper = null;
  document.body.innerHTML = "";
});

const CASH_FLOW_STEPS: CalcStep[] = [
  {
    label: "Net Operating Income (NOI)",
    value: 1800,
    unit: "money",
    formula: "Rent ($2,600) − Operating Expenses ($800) = $1,800",
    terms: [
      { label: "Rent", value: 2600, sign: "+" },
      { label: "Operating Expenses", value: 800, sign: "-" },
    ],
  },
  {
    label: "Monthly Mortgage Payment",
    value: 1714.96,
    unit: "money",
    formula: "Refi Loan ($150,000) amortized at 7%/yr over 30 years = $1,714.96",
    note: "A 0% loan repays straight-line: loan ÷ number of months.",
  },
  {
    label: "Monthly Cash Flow",
    value: 85.04,
    unit: "money",
    formula: "NOI ($1,800) − Mortgage ($1,714.96) = $85.04",
    terms: [
      { label: "NOI", value: 1800, sign: "+" },
      { label: "Mortgage", value: 1714.96, sign: "-" },
    ],
  },
];

const mountPopup = (props: Record<string, unknown> = {}) =>
  mount(CalculationBreakdownPopup, {
    attachTo: document.body,
    props: {
      open: true,
      metricLabel: "Cash Flow",
      metricKey: "cash_flow",
      steps: CASH_FLOW_STEPS,
      ...props,
    },
  });

const popup = () => document.querySelector('[data-testid="calculation-breakdown-popup"]');
const dialog = () => document.querySelector('[role="dialog"]');
const textsOf = (selector: string) =>
  [...document.querySelectorAll(selector)].map((el) => el.textContent?.replace(/\s+/g, " ").trim());

describe("CalculationBreakdownPopup", () => {
  it("renders nothing while closed", async () => {
    wrapper = mountPopup({ open: false });
    await nextTick();
    expect(popup()).toBeNull();
  });

  it("teleports a dialog to body, named 'How <metric> is calculated', with the last step as the headline", async () => {
    wrapper = mountPopup();
    await nextTick();
    expect(popup()).not.toBeNull();
    expect(popup()!.getAttribute("data-metric-key")).toBe("cash_flow");
    const heading = document.querySelector("h2")!;
    expect(heading.textContent?.trim()).toBe("How Cash Flow is calculated");
    expect(dialog()!.getAttribute("aria-labelledby")).toBe(heading.id);
    expect(document.querySelector('[data-part="headline-value"]')!.textContent?.trim()).toBe("$85.04");
  });

  it("lists every step in order with its label and unit-formatted value; the last one is marked as the headline", async () => {
    wrapper = mountPopup();
    await nextTick();
    expect(textsOf('[data-part="step-label"]')).toEqual([
      "Net Operating Income (NOI)",
      "Monthly Mortgage Payment",
      "Monthly Cash Flow",
    ]);
    expect(textsOf('[data-part="step-value"]')).toEqual(["$1,800", "$1,714.96", "$85.04"]);
    const items = document.querySelectorAll('[data-part="steps"] > li');
    expect(items).toHaveLength(3);
    expect(items[0]!.getAttribute("data-part")).toBe("step");
    expect(items[2]!.getAttribute("data-part")).toBe("headline-step");
  });

  it("stacks a sum-type step's terms with their sign, and shows the formula text on every other step", async () => {
    wrapper = mountPopup();
    await nextTick();
    const items = document.querySelectorAll('[data-part="steps"] > li');
    const noiTerms = [...items[0]!.querySelectorAll('[data-part="step-term"]')].map((el) => [
      el.querySelector('[data-part="term-sign"]')!.textContent!.trim(),
      el.querySelector('[data-part="term-label"]')!.textContent!.trim(),
      el.querySelector('[data-part="term-value"]')!.textContent!.trim(),
    ]);
    expect(noiTerms).toEqual([
      ["+", "Rent", "$2,600"],
      ["-", "Operating Expenses", "$800"],
    ]);
    expect(items[0]!.querySelector('[data-part="step-formula"]')).toBeNull();
    expect(items[1]!.querySelector('[data-part="step-terms"]')).toBeNull();
    expect(items[1]!.querySelector('[data-part="step-formula"]')!.textContent?.trim()).toBe(
      "Refi Loan ($150,000) amortized at 7%/yr over 30 years = $1,714.96",
    );
  });

  it("prints a step's note under it, and nothing where there is none", async () => {
    wrapper = mountPopup();
    await nextTick();
    expect(textsOf('[data-part="step-note"]')).toEqual([
      "A 0% loan repays straight-line: loan ÷ number of months.",
    ]);
  });

  it("formats percentage and ratio steps by their unit, including the ±∞ sentinels", async () => {
    wrapper = mountPopup({
      metricLabel: "ROI",
      metricKey: "roi",
      steps: [
        { label: "DSCR", value: 1.2, unit: "ratio", formula: "Rent ($2,600) ÷ PITIA ($2,166.67) = 1.2" },
        { label: "Cash on Cash", value: -2, unit: "pct", formula: "Cash Flow ≤ 0 → return undefined (-∞)" },
        { label: "ROI", value: 19.87, unit: "pct", formula: "… = 19.87%" },
      ] satisfies CalcStep[],
    });
    await nextTick();
    expect(textsOf('[data-part="step-value"]')).toEqual(["1.20x", "-∞%", "19.87%"]);
    expect(document.querySelector('[data-part="headline-value"]')!.textContent?.trim()).toBe("19.87%");
  });

  it("marks the step carrying the tile's own value as the headline when the section ends on a derived reading", async () => {
    wrapper = mountPopup({
      metricLabel: "Cash-Out Routi (Lowest ARV)",
      metricKey: "cash_out_routi_conservative",
      metricValue: -17417.5,
      steps: [
        { label: "Refi Loan (Lowest ARV)", value: 216000, unit: "money", formula: "Lowest ARV (,000) × LTV 75% = ,000" },
        { label: "Cash-Out Wire (Lowest ARV)", value: -17417.5, unit: "money", formula: "… = -,417.50" },
        { label: "Cash to Refi Table (Lowest ARV)", value: 17417.5, unit: "money", formula: "Wire (-,417.50) is negative → ,417.50 brought to the table" },
      ] satisfies CalcStep[],
    });
    await nextTick();
    expect(document.querySelector('[data-part="headline-value"]')!.textContent?.trim()).toBe("-$17,417.50");
    const items = document.querySelectorAll('[data-part="steps"] > li');
    expect(items[1]!.getAttribute("data-part")).toBe("headline-step");
    expect(items[2]!.getAttribute("data-part")).toBe("step");
  });

  it("falls back to the last step as the headline when the tile's value matches no step", async () => {
    wrapper = mountPopup({ metricValue: 999999 });
    await nextTick();
    expect(document.querySelector('[data-part="headline-value"]')!.textContent?.trim()).toBe("$85.04");
  });

  it("says so when the analysis carried no breakdown for this result", async () => {
    wrapper = mountPopup({ steps: undefined });
    await nextTick();
    expect(document.querySelector('[data-part="empty"]')!.textContent).toContain("No breakdown available");
    expect(document.querySelector('[data-part="headline-value"]')).toBeNull();
    wrapper.unmount();
    wrapper = mountPopup({ steps: [] });
    await nextTick();
    expect(document.querySelector('[data-part="empty"]')).not.toBeNull();
  });

  it("closes on Escape, on the scrim and from its close button — and not from a click inside the panel", async () => {
    wrapper = mountPopup();
    await nextTick();
    document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
    (popup() as HTMLElement).click();
    (document.querySelector('[data-part="close"]') as HTMLElement).click();
    (dialog() as HTMLElement).click();
    await nextTick();
    expect(wrapper.emitted("close")).toHaveLength(3);
  });

  it("claims the Escape it handles and ignores one already claimed above it", async () => {
    wrapper = mountPopup();
    await nextTick();
    const escape = new KeyboardEvent("keydown", { key: "Escape", bubbles: true, cancelable: true });
    document.dispatchEvent(escape);
    expect(escape.defaultPrevented).toBe(true);
    const claimed = new KeyboardEvent("keydown", { key: "Escape", bubbles: true, cancelable: true });
    claimed.preventDefault();
    document.dispatchEvent(claimed);
    await nextTick();
    expect(wrapper.emitted("close")).toHaveLength(1);
  });

  it("listens for Escape only while open", async () => {
    wrapper = mountPopup({ open: false });
    await nextTick();
    document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
    expect(wrapper.emitted("close")).toBeUndefined();
    await wrapper.setProps({ open: true });
    await nextTick();
    await wrapper.setProps({ open: false });
    await nextTick();
    document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
    expect(wrapper.emitted("close")).toBeUndefined();
  });

  it("moves focus into the panel on open, makes the rest of the page inert, and restores focus on close", async () => {
    const pressedTile = document.createElement("button");
    pressedTile.id = "pressed-tile";
    document.body.appendChild(pressedTile);
    pressedTile.focus();
    wrapper = mountPopup({ open: false });
    await wrapper.setProps({ open: true });
    await nextTick();
    await nextTick();
    expect(document.activeElement).toBe(dialog());
    expect(pressedTile.hasAttribute("inert")).toBe(true);
    await wrapper.setProps({ open: false });
    await nextTick();
    expect(pressedTile.hasAttribute("inert")).toBe(false);
    expect(document.activeElement?.id).toBe("pressed-tile");
  });
});
