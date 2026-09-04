// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { mount } from "@vue/test-utils";

import SendOfferModal from "./SendOfferModal.vue";
import api from "../api";

vi.mock("../api", () => ({
  default: { sendOffer: vi.fn() },
  apiClient: { get: vi.fn(), post: vi.fn(), put: vi.fn(), delete: vi.fn() },
}));

const sendOffer = vi.mocked(api.sendOffer);

function mountModal(isOpen = true) {
  return mount(SendOfferModal, { props: { isOpen } });
}

type Modal = ReturnType<typeof mountModal>;

/** Fill every field the modal treats as required. */
async function fillRequired(wrapper: Modal) {
  await wrapper.find('[data-testid="offer.agent-name"]').setValue("John Doe");
  await wrapper.find('[data-testid="offer.agent-email"]').setValue("john@example.com");
  await wrapper
    .find('[data-testid="offer.property-address"]')
    .setValue("123 Main St");
  // The price field is a MoneyInput: focus, type, blur is its commit cycle.
  const price = wrapper.find('[data-testid="offer.purchase-price"] [data-part="input"]');
  await price.trigger("focus");
  await price.setValue("250000");
  await price.trigger("blur");
}

const messageText = (wrapper: Modal) =>
  wrapper.find('[data-testid="offer.message"]').text();

describe("SendOfferModal", () => {
  beforeEach(() => {
    sendOffer.mockReset();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it("renders nothing while closed", () => {
    const wrapper = mountModal(false);
    expect(wrapper.find('[data-testid="offer.root"]').exists()).toBe(false);
    expect(wrapper.text()).toBe("");
  });

  it("renders the dialog once opened", () => {
    expect(mountModal().find('[data-testid="offer.root"]').exists()).toBe(true);
    expect(mountModal().text()).toContain("Send Market Offer");
  });

  describe("validation", () => {
    it("refuses to send with the required fields empty, and calls no API", async () => {
      const wrapper = mountModal();

      await wrapper.find('[data-testid="offer.send"]').trigger("click");

      expect(messageText(wrapper)).toBe("Please fill in all required fields.");
      expect(sendOffer).not.toHaveBeenCalled();
    });

    it.each([
      ["offer.agent-name"],
      ["offer.agent-email"],
      ["offer.property-address"],
    ])("refuses to send when %s is missing", async (missing) => {
      const wrapper = mountModal();
      await fillRequired(wrapper);
      await wrapper.find(`[data-testid="${missing}"]`).setValue("");

      await wrapper.find('[data-testid="offer.send"]').trigger("click");

      expect(messageText(wrapper)).toBe("Please fill in all required fields.");
      expect(sendOffer).not.toHaveBeenCalled();
    });
  });

  describe("sending", () => {
    it("posts exactly what was typed", async () => {
      sendOffer.mockResolvedValue({ success: true, message: "ok" });
      const wrapper = mountModal();
      await fillRequired(wrapper);
      await wrapper.find('[data-testid="offer.inspection-days"]').setValue("7");

      await wrapper.find('[data-testid="offer.send"]').trigger("click");

      expect(sendOffer).toHaveBeenCalledWith({
        agent_name: "John Doe",
        agent_email: "john@example.com",
        property_address: "123 Main St",
        purchase_price: 250000,
        inspection_period_days: 7,
      });
    });

    it("confirms success, then closes and clears the form after 1500 ms", async () => {
      vi.useFakeTimers();
      sendOffer.mockResolvedValue({ success: true, message: "Queued for delivery" });
      const wrapper = mountModal();
      await fillRequired(wrapper);

      await wrapper.find('[data-testid="offer.send"]').trigger("click");
      await vi.advanceTimersByTimeAsync(0);

      // The confirmation is the component's own copy, not the server's message.
      expect(messageText(wrapper)).toBe("Offer sent successfully!");
      expect(wrapper.emitted("close")).toBeUndefined();

      await vi.advanceTimersByTimeAsync(1499);
      expect(wrapper.emitted("close")).toBeUndefined();

      await vi.advanceTimersByTimeAsync(1);
      expect(wrapper.emitted("close")).toHaveLength(1);
      expect(
        wrapper.find<HTMLInputElement>('[data-testid="offer.agent-name"]').element.value,
      ).toBe("");
      expect(
        wrapper.find<HTMLInputElement>('[data-testid="offer.property-address"]')
          .element.value,
      ).toBe("");
    });

    it("shows the server's message when the send is refused", async () => {
      sendOffer.mockResolvedValue({ success: false, message: "Agent email bounced" });
      const wrapper = mountModal();
      await fillRequired(wrapper);

      await wrapper.find('[data-testid="offer.send"]').trigger("click");
      await vi.waitFor(() =>
        expect(messageText(wrapper)).toBe("Agent email bounced"),
      );
      expect(wrapper.emitted("close")).toBeUndefined();
    });

    it("falls back to its own copy when a refusal carries no message", async () => {
      sendOffer.mockResolvedValue({ success: false, message: "" });
      const wrapper = mountModal();
      await fillRequired(wrapper);

      await wrapper.find('[data-testid="offer.send"]').trigger("click");
      await vi.waitFor(() =>
        expect(messageText(wrapper)).toBe("Failed to send offer."),
      );
    });

    it("surfaces the API error detail when the request throws", async () => {
      sendOffer.mockRejectedValue({
        response: { data: { detail: "SMTP is not configured" } },
      });
      const wrapper = mountModal();
      await fillRequired(wrapper);

      await wrapper.find('[data-testid="offer.send"]').trigger("click");
      await vi.waitFor(() =>
        expect(messageText(wrapper)).toBe("SMTP is not configured"),
      );
    });

    it("falls back to its own copy for an error with no detail", async () => {
      sendOffer.mockRejectedValue(new Error("network down"));
      const wrapper = mountModal();
      await fillRequired(wrapper);

      await wrapper.find('[data-testid="offer.send"]').trigger("click");
      await vi.waitFor(() =>
        expect(messageText(wrapper)).toBe("An unexpected error occurred."),
      );
    });

    it("disables the send button while the request is in flight", async () => {
      let release: (value: { success: boolean; message: string }) => void = () => {};
      sendOffer.mockReturnValue(
        new Promise((resolve) => {
          release = resolve;
        }),
      );
      const wrapper = mountModal();
      await fillRequired(wrapper);
      const button = () => wrapper.find('[data-testid="offer.send"]');

      expect(button().attributes("disabled")).toBeUndefined();

      await button().trigger("click");
      expect(button().attributes("disabled")).toBeDefined();
      expect(button().text()).toBe("Sending...");

      release({ success: false, message: "done" });
      await vi.waitFor(() =>
        expect(button().attributes("disabled")).toBeUndefined(),
      );
      expect(button().text()).toBe("Send Offer");
    });
  });

  describe("dismissing", () => {
    it.each(["offer.close", "offer.cancel"])("emits close from %s", async (id) => {
      const wrapper = mountModal();
      await wrapper.find(`[data-testid="${id}"]`).trigger("click");
      expect(wrapper.emitted("close")).toHaveLength(1);
    });

    it("clears a stale message when reopened after a dismissal", async () => {
      const wrapper = mountModal();
      await wrapper.find('[data-testid="offer.send"]').trigger("click");
      expect(wrapper.find('[data-testid="offer.message"]').exists()).toBe(true);

      await wrapper.find('[data-testid="offer.cancel"]').trigger("click");
      expect(wrapper.find('[data-testid="offer.message"]').exists()).toBe(false);
    });
  });
});
