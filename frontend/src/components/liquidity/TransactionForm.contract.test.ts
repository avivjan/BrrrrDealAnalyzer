// @vitest-environment jsdom
import { afterEach, describe, expect, it } from "vitest";
import { DOMWrapper, mount } from "@vue/test-utils";

import TransactionForm from "./TransactionForm.vue";
import { todayISO } from "../../utils/liquidityEngine";
import type {
  LiquidityRecurringTransaction,
  LiquidityTransaction,
} from "../../types/liquidity";

/**
 * The form teleports to `<body>`, so nothing it renders is inside the
 * wrapper's own element — every query goes through the document.
 */
type Props = {
  editTxn?: LiquidityTransaction | null;
  editRecurring?: LiquidityRecurringTransaction | null;
  prefillDate?: string | null;
};

/** Mount closed, then open: the seeding watcher hangs off the `open` prop. */
async function openForm(props: Props = {}) {
  const wrapper = mount(TransactionForm, { props: { open: false, ...props } });
  await wrapper.setProps({ open: true });
  return wrapper;
}

type Form = Awaited<ReturnType<typeof openForm>>;

function at(testid: string): DOMWrapper<HTMLElement> {
  const el = document.querySelector(`[data-testid="${testid}"]`);
  expect(el, `no element with data-testid="${testid}"`).toBeTruthy();
  return new DOMWrapper(el as HTMLElement);
}

const exists = (testid: string) =>
  document.querySelector(`[data-testid="${testid}"]`) !== null;

const value = (testid: string) => (at(testid).element as HTMLInputElement).value;

/** The last `save` payload the form emitted, if any. */
function lastSave(wrapper: Form) {
  const events = wrapper.emitted("save");
  return events ? events[events.length - 1]![0] : undefined;
}

/** The minimum a one-off needs to be valid. */
async function fillOneOff(amount = "49.2", description = "Rehab draw #2") {
  await at("txnform.amount").setValue(amount);
  await at("txnform.description").setValue(description);
}

describe("TransactionForm", () => {
  afterEach(() => {
    document.body.innerHTML = "";
  });

  it("renders nothing while closed", () => {
    mount(TransactionForm, { props: { open: false } });
    expect(exists("txnform.root")).toBe(false);
  });

  describe("a one-off transaction", () => {
    it("saves an outflow as a negative amount", async () => {
      const wrapper = await openForm();
      await fillOneOff();
      await at("txnform.date").setValue("2026-04-01");
      await at("txnform.outflow").trigger("click");

      await at("txnform.save").trigger("click");

      expect(lastSave(wrapper)).toEqual({
        kind: "transaction",
        id: undefined,
        effective_date: "2026-04-01",
        description: "Rehab draw #2",
        amount_k: -49.2,
      });
    });

    it("saves an inflow as a positive amount", async () => {
      const wrapper = await openForm();
      await fillOneOff("12.5", "Rent");
      await at("txnform.date").setValue("2026-04-01");
      await at("txnform.inflow").trigger("click");

      await at("txnform.save").trigger("click");

      expect(lastSave(wrapper)).toMatchObject({
        kind: "transaction",
        amount_k: 12.5,
      });
    });

    it("trims the description", async () => {
      const wrapper = await openForm();
      await fillOneOff("10", "   Padded   ");
      await at("txnform.save").trigger("click");

      expect(lastSave(wrapper)).toMatchObject({ description: "Padded" });
    });

    it("defaults the date to today", async () => {
      await openForm();
      expect(value("txnform.date")).toBe(todayISO());
    });

    it("takes the prefill date the calendar passed in", async () => {
      await openForm({ prefillDate: "2026-07-04" });
      expect(value("txnform.date")).toBe("2026-07-04");
    });
  });

  describe("seeding from an existing row", () => {
    it("fills the fields from editTxn and sends its id back", async () => {
      const wrapper = await openForm({
        editTxn: {
          id: "txn-9",
          effective_date: "2026-02-14",
          description: "HM interest",
          amount_k: -3.25,
        },
      });

      expect(value("txnform.amount")).toBe("3.25");
      expect(value("txnform.description")).toBe("HM interest");
      expect(value("txnform.date")).toBe("2026-02-14");
      // Editing locks the one-off/recurring choice.
      expect(exists("txnform.mode-recurring")).toBe(false);
      expect(at("txnform.save").text()).toBe("Update");

      await at("txnform.save").trigger("click");
      expect(lastSave(wrapper)).toMatchObject({
        kind: "transaction",
        id: "txn-9",
        amount_k: -3.25,
      });
    });

    it("fills the schedule from editRecurring", async () => {
      await openForm({
        editRecurring: {
          id: "rule-3",
          description: "Insurance",
          amount_k: -1.1,
          start_date: "2026-01-15",
          end_date: null,
          occurrences: 6,
          frequency: "quarterly",
          interval: 2,
        },
      });

      expect(value("txnform.amount")).toBe("1.1");
      expect(value("txnform.start-date")).toBe("2026-01-15");
      expect(value("txnform.frequency")).toBe("quarterly");
      expect(value("txnform.interval")).toBe("2");
      expect(value("txnform.occurrences")).toBe("6");
    });

    it("reads an end date as the 'on date' mode", async () => {
      await openForm({
        editRecurring: {
          id: "rule-4",
          description: "Loan",
          amount_k: 5,
          start_date: "2026-01-15",
          end_date: "2026-12-31",
          occurrences: null,
          frequency: "monthly",
          interval: 1,
        },
      });

      expect(value("txnform.end-date")).toBe("2026-12-31");
      expect(exists("txnform.occurrences")).toBe(false);
    });
  });

  describe("a recurring series", () => {
    it("saves an open-ended series with no end date and no occurrence count", async () => {
      const wrapper = await openForm();
      await at("txnform.mode-recurring").trigger("click");
      await at("txnform.amount").setValue("2.5");
      await at("txnform.description").setValue("HOA");
      await at("txnform.start-date").setValue("2026-03-01");
      await at("txnform.frequency").setValue("weekly");
      await at("txnform.interval").setValue("2");

      await at("txnform.save").trigger("click");

      expect(lastSave(wrapper)).toEqual({
        kind: "recurring",
        id: undefined,
        description: "HOA",
        amount_k: -2.5,
        start_date: "2026-03-01",
        end_date: null,
        occurrences: null,
        frequency: "weekly",
        interval: 2,
      });
    });

    it("saves an end date when the series ends on a date", async () => {
      const wrapper = await openForm();
      await at("txnform.mode-recurring").trigger("click");
      await at("txnform.amount").setValue("2.5");
      await at("txnform.description").setValue("HOA");
      await at("txnform.start-date").setValue("2026-03-01");
      await at("txnform.end-on").trigger("click");
      await at("txnform.end-date").setValue("2026-09-01");

      await at("txnform.save").trigger("click");

      expect(lastSave(wrapper)).toMatchObject({
        kind: "recurring",
        end_date: "2026-09-01",
        occurrences: null,
      });
    });

    it("saves an occurrence count when the series ends after N", async () => {
      const wrapper = await openForm();
      await at("txnform.mode-recurring").trigger("click");
      await at("txnform.amount").setValue("2.5");
      await at("txnform.description").setValue("HOA");
      await at("txnform.end-after").trigger("click");
      await at("txnform.occurrences").setValue("4");

      await at("txnform.save").trigger("click");

      expect(lastSave(wrapper)).toMatchObject({
        kind: "recurring",
        end_date: null,
        occurrences: 4,
      });
    });

    it("falls back to an interval of 1 when the box is emptied", async () => {
      const wrapper = await openForm();
      await at("txnform.mode-recurring").trigger("click");
      await at("txnform.amount").setValue("2.5");
      await at("txnform.description").setValue("HOA");
      await at("txnform.interval").setValue("");

      await at("txnform.save").trigger("click");

      expect(lastSave(wrapper)).toMatchObject({ interval: 1 });
    });

    it("previews the first occurrences before saving", async () => {
      await openForm();
      await at("txnform.mode-recurring").trigger("click");
      await at("txnform.amount").setValue("2.5");
      await at("txnform.description").setValue("HOA");
      await at("txnform.start-date").setValue("2026-03-01");
      await at("txnform.frequency").setValue("monthly");

      expect(exists("txnform.preview.0")).toBe(true);
      expect(at("txnform.preview.0").text()).toContain("Mar 1, 2026");
      expect(at("txnform.preview.1").text()).toContain("Apr 1, 2026");
    });
  });

  describe("when Save is refused", () => {
    it("starts disabled with an empty form", async () => {
      await openForm();
      expect(at("txnform.save").attributes("disabled")).toBeDefined();
    });

    it("stays disabled without a description", async () => {
      await openForm();
      await at("txnform.amount").setValue("10");
      expect(at("txnform.save").attributes("disabled")).toBeDefined();
    });

    it("stays disabled for a zero or negative amount", async () => {
      await openForm();
      await at("txnform.description").setValue("Something");
      await at("txnform.amount").setValue("0");
      expect(at("txnform.save").attributes("disabled")).toBeDefined();
      await at("txnform.amount").setValue("-5");
      expect(at("txnform.save").attributes("disabled")).toBeDefined();
    });

    it("stays disabled when a series would end before it starts", async () => {
      await openForm();
      await at("txnform.mode-recurring").trigger("click");
      await at("txnform.amount").setValue("1");
      await at("txnform.description").setValue("Bad range");
      await at("txnform.start-date").setValue("2026-06-01");
      await at("txnform.end-on").trigger("click");
      await at("txnform.end-date").setValue("2026-01-01");

      expect(at("txnform.save").attributes("disabled")).toBeDefined();
    });

    it("enables once amount and description are both present", async () => {
      await openForm();
      await fillOneOff();
      expect(at("txnform.save").attributes("disabled")).toBeUndefined();
    });

    it("emits nothing if Save is invoked while invalid", async () => {
      const wrapper = await openForm();
      await at("txnform.save").trigger("click");
      expect(wrapper.emitted("save")).toBeUndefined();
    });
  });

  describe("keyboard and dismissal", () => {
    it("closes on Escape", async () => {
      const wrapper = await openForm();
      await at("txnform.root").trigger("keydown", { key: "Escape" });
      expect(wrapper.emitted("close")).toHaveLength(1);
    });

    it("saves on ⌘+Enter when the form is valid", async () => {
      const wrapper = await openForm();
      await fillOneOff();

      await at("txnform.root").trigger("keydown", { key: "Enter", metaKey: true });

      expect(wrapper.emitted("save")).toHaveLength(1);
    });

    it("ignores ⌘+Enter while the form is invalid", async () => {
      const wrapper = await openForm();
      await at("txnform.root").trigger("keydown", { key: "Enter", metaKey: true });
      expect(wrapper.emitted("save")).toBeUndefined();
    });

    it("ignores Ctrl+Enter — today only the ⌘ key saves", async () => {
      // Documented as-is: `onKeyDown` tests `e.metaKey` only, so the Windows /
      // Linux chord does nothing. Changing that is a behaviour change.
      const wrapper = await openForm();
      await fillOneOff();

      await at("txnform.root").trigger("keydown", { key: "Enter", ctrlKey: true });

      expect(wrapper.emitted("save")).toBeUndefined();
    });

    it("closes from Cancel and from the backdrop", async () => {
      const wrapper = await openForm();
      await at("txnform.cancel").trigger("click");
      await at("txnform.backdrop").trigger("click");
      expect(wrapper.emitted("close")).toHaveLength(2);
    });
  });
});
