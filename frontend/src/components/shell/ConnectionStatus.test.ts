// @vitest-environment jsdom
import { describe, expect, it } from "vitest";
import { mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";

import { useConnectionStore } from "../../stores/connectionStore";
import ConnectionStatus from "./ConnectionStatus.vue";

function mountWith(state: { isChecking: boolean; isConnected: boolean }) {
  const pinia = createPinia();
  setActivePinia(pinia);
  const store = useConnectionStore();
  store.isChecking = state.isChecking;
  store.isConnected = state.isConnected;
  return mount(ConnectionStatus, { global: { plugins: [pinia] } });
}

describe("ConnectionStatus", () => {
  it("keeps the v1 hook, role and live region", () => {
    const wrapper = mountWith({ isChecking: false, isConnected: true });
    expect(wrapper.attributes("data-testid")).toBe("app.status");
    expect(wrapper.attributes("role")).toBe("status");
    expect(wrapper.attributes("aria-live")).toBe("polite");
  });

  it.each([
    [{ isChecking: true, isConnected: false }, "Connecting to server...", "bg-negative"],
    [{ isChecking: false, isConnected: true }, "Server Connected", "bg-positive"],
    [{ isChecking: false, isConnected: false }, "Disconnected", "bg-negative"],
  ])("says %j as %s", (state, text, dot) => {
    const wrapper = mountWith(state);
    expect(wrapper.attributes("title")).toBe(text);
    expect(wrapper.attributes("aria-label")).toBe(text);
    expect(wrapper.text()).toBe(text);
    expect(wrapper.find("span[aria-hidden]").classes()).toContain(dot);
  });
});
