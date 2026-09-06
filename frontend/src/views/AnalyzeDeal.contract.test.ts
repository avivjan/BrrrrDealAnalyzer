// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createPinia, setActivePinia } from "pinia";
import { flushPromises, mount } from "@vue/test-utils";
import PrimeVue from "primevue/config";

import AnalyzeDeal from "./AnalyzeDeal.vue";
import api from "../api";
import type { ActiveDealRes } from "../types";

const routerPush = vi.fn();

vi.mock("vue-router", () => ({
  useRoute: () => ({ query: {} }),
  useRouter: () => ({ push: routerPush, replace: vi.fn() }),
}));

vi.mock("../api", () => ({
  default: { saveActiveDeal: vi.fn() },
  apiClient: { get: vi.fn(), post: vi.fn(), put: vi.fn(), delete: vi.fn() },
}));

const saveActiveDeal = vi.mocked(api.saveActiveDeal);

function mountView() {
  return mount(AnalyzeDeal, {
    global: { plugins: [[PrimeVue, { unstyled: true }]] },
  });
}

type View = ReturnType<typeof mountView>;

/**
 * A money field commits on blur, so focus / type / blur is the whole cycle.
 * `data-part="input"` is the real element inside each primitive.
 */
async function typeMoney(wrapper: View, key: string, text: string) {
  const input = wrapper.find(`[data-testid="form.field.${key}"] [data-part="input"]`);
  await input.trigger("focus");
  await input.setValue(text);
  await input.trigger("blur");
}

/** The minimum a BRRRR form needs to clear `validateDealInputs`. */
async function fillValidBrrr(wrapper: View) {
  await typeMoney(wrapper, "purchasePrice", "200");
  await typeMoney(wrapper, "arv_in_thousands", "320");
  await typeMoney(wrapper, "rent", "2600");
}

const errors = (wrapper: View) =>
  wrapper.findAll('[data-testid^="analyze.error."]').map((el) => el.text());

const modalOpen = (wrapper: View) =>
  wrapper.find('[data-testid="analyze.modal"]').exists();

const savedDeal: ActiveDealRes = {
  deal_type: "BRRRR",
  id: "new-deal-1",
  created_at: "2026-05-01T09:00:00.000Z",
  updated_at: "2026-05-01T09:00:00.000Z",
  address: "123 Main St",
  section: 1,
  stage: 2,
} as ActiveDealRes;

describe("AnalyzeDeal", () => {
  let quiet: ReturnType<typeof vi.spyOn>[];

  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
    quiet = (["group", "groupEnd", "log"] as const).map((m) =>
      vi.spyOn(console, m).mockImplementation(() => {}),
    );
    saveActiveDeal.mockResolvedValue(savedDeal);
  });

  afterEach(() => {
    for (const spy of quiet) spy.mockRestore();
  });

  describe("Analyze & Save on an invalid form", () => {
    it("lists the validation errors and opens no modal", async () => {
      const wrapper = mountView();

      await wrapper.find('[data-testid="analyze.analyze-save"]').trigger("click");

      expect(errors(wrapper)).toEqual([
        "Purchase price (in thousands) must be greater than 0.",
        "ARV (in thousands) must be greater than 0.",
        "Rent must be greater than 0.",
      ]);
      expect(modalOpen(wrapper)).toBe(false);
      expect(saveActiveDeal).not.toHaveBeenCalled();
    });

    it("validates against the selected deal type", async () => {
      const wrapper = mountView();
      await wrapper.find('[data-testid="analyze.type-flip"]').trigger("click");

      await wrapper.find('[data-testid="analyze.analyze-save"]').trigger("click");

      // The blank form already carries a 6-month holding time, so only the
      // price fields are missing on the FLIP side.
      expect(errors(wrapper)).toEqual([
        "Purchase price (in thousands) must be greater than 0.",
        "Sale Price (ARV) must be greater than 0.",
      ]);
      expect(errors(wrapper)).not.toContain("Rent must be greater than 0.");
    });

    it("clears the errors once the form is fixed", async () => {
      const wrapper = mountView();
      await wrapper.find('[data-testid="analyze.analyze-save"]').trigger("click");
      expect(errors(wrapper)).not.toHaveLength(0);

      await fillValidBrrr(wrapper);
      await wrapper.find('[data-testid="analyze.analyze-save"]').trigger("click");

      expect(wrapper.find('[data-testid="analyze.errors"]').exists()).toBe(false);
    });
  });

  describe("Analyze & Save on a valid form", () => {
    it("opens the save modal without touching the API", async () => {
      const wrapper = mountView();
      await fillValidBrrr(wrapper);

      await wrapper.find('[data-testid="analyze.analyze-save"]').trigger("click");

      expect(modalOpen(wrapper)).toBe(true);
      expect(saveActiveDeal).not.toHaveBeenCalled();
    });
  });

  describe("the save modal", () => {
    async function openModal() {
      const wrapper = mountView();
      await fillValidBrrr(wrapper);
      await wrapper.find('[data-testid="analyze.analyze-save"]').trigger("click");
      return wrapper;
    }

    it("refuses an empty address and calls nothing", async () => {
      const wrapper = await openModal();

      await wrapper.find('[data-testid="analyze.modal.save"]').trigger("click");
      await flushPromises();

      expect(wrapper.find('[data-testid="analyze.modal.error"]').text()).toContain(
        "Property address is required.",
      );
      expect(saveActiveDeal).not.toHaveBeenCalled();
      expect(routerPush).not.toHaveBeenCalled();
      expect(modalOpen(wrapper)).toBe(true);
    });

    it("treats whitespace as no address at all", async () => {
      const wrapper = await openModal();
      await wrapper.find('[data-testid="analyze.modal.address"]').setValue("   ");

      await wrapper.find('[data-testid="analyze.modal.save"]').trigger("click");
      await flushPromises();

      expect(saveActiveDeal).not.toHaveBeenCalled();
    });

    it("saves the deal inputs merged with the modal's own fields", async () => {
      const wrapper = await openModal();
      await wrapper.find('[data-testid="analyze.modal.address"]').setValue("123 Main St");
      await wrapper.find('[data-testid="analyze.modal.section"]').setValue(3);
      await wrapper.find('[data-testid="analyze.modal.stage"]').setValue(4);

      await wrapper.find('[data-testid="analyze.modal.save"]').trigger("click");
      await flushPromises();

      expect(saveActiveDeal).toHaveBeenCalledTimes(1);
      expect(saveActiveDeal.mock.calls[0]![0]).toMatchObject({
        deal_type: "BRRRR",
        address: "123 Main St",
        section: 3,
        stage: 4,
        purchasePrice: 200,
        arv_in_thousands: 320,
        rent: 2600,
      });
    });

    it("hands the new deal to My Deals through the query string", async () => {
      const wrapper = await openModal();
      await wrapper.find('[data-testid="analyze.modal.address"]').setValue("123 Main St");
      await wrapper.find('[data-testid="analyze.modal.section"]').setValue(2);

      await wrapper.find('[data-testid="analyze.modal.save"]').trigger("click");
      await flushPromises();

      expect(routerPush).toHaveBeenCalledWith({
        path: "/my-deals",
        query: {
          openDeal: "new-deal-1",
          dealType: "BRRRR",
          section: "2",
        },
      });
      expect(modalOpen(wrapper)).toBe(false);
    });

    it("saves on Enter in the address box", async () => {
      const wrapper = await openModal();
      const address = wrapper.find('[data-testid="analyze.modal.address"]');
      await address.setValue("123 Main St");

      await address.trigger("keyup.enter");
      await flushPromises();

      expect(saveActiveDeal).toHaveBeenCalledTimes(1);
    });

    it("keeps the modal open and reports a failed save", async () => {
      const error = vi.spyOn(console, "error").mockImplementation(() => {});
      saveActiveDeal.mockRejectedValue(new Error("500"));
      const wrapper = await openModal();
      await wrapper.find('[data-testid="analyze.modal.address"]').setValue("123 Main St");

      await wrapper.find('[data-testid="analyze.modal.save"]').trigger("click");
      await flushPromises();

      expect(wrapper.find('[data-testid="analyze.modal.error"]').text()).toContain(
        "Failed to save deal. Please try again.",
      );
      expect(modalOpen(wrapper)).toBe(true);
      expect(routerPush).not.toHaveBeenCalled();
      error.mockRestore();
    });

    it("disables both buttons while the save is in flight", async () => {
      let release: (deal: ActiveDealRes) => void = () => {};
      saveActiveDeal.mockReturnValue(
        new Promise((resolve) => {
          release = resolve;
        }),
      );
      const wrapper = await openModal();
      await wrapper.find('[data-testid="analyze.modal.address"]').setValue("123 Main St");

      await wrapper.find('[data-testid="analyze.modal.save"]').trigger("click");
      await wrapper.vm.$nextTick();

      const save = wrapper.find('[data-testid="analyze.modal.save"]');
      expect(save.attributes("disabled")).toBeDefined();
      expect(save.text()).toBe("Saving...");
      expect(
        wrapper.find('[data-testid="analyze.modal.cancel"]').attributes("disabled"),
      ).toBeDefined();

      release(savedDeal);
      await flushPromises();
    });

    it("closes on Cancel without saving", async () => {
      const wrapper = await openModal();

      await wrapper.find('[data-testid="analyze.modal.cancel"]').trigger("click");

      expect(modalOpen(wrapper)).toBe(false);
      expect(saveActiveDeal).not.toHaveBeenCalled();
    });
  });

  describe("the deal type switch", () => {
    it("swaps the form's fields", async () => {
      const wrapper = mountView();
      expect(wrapper.text()).toContain("Refinance (BRRRR)");

      await wrapper.find('[data-testid="analyze.type-flip"]').trigger("click");

      expect(wrapper.text()).toContain("Flip Strategy");
      expect(wrapper.text()).not.toContain("Refinance (BRRRR)");
    });

    it("keeps ARV and Sale Price in step, whichever side is typed", async () => {
      const wrapper = mountView();
      await typeMoney(wrapper, "arv_in_thousands", "320");

      await wrapper.find('[data-testid="analyze.type-flip"]').trigger("click");

      expect(
        wrapper
          .find<HTMLInputElement>('[data-testid="form.field.salePrice"] [data-part="input"]')
          .element.value,
      ).toBe("$320,000");
    });
  });
});
