// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { flushPromises, mount, type VueWrapper } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";

/**
 * App.vue fetches the deals for the dashboard only after the first navigation
 * has loaded the session (which renews an expired one). Fetching earlier hit
 * a 401 and left the dashboard empty until a manual reload.
 */

const fakeRouter = vi.hoisted(() => {
  let markFirstNavigationDone: () => void = () => {};
  return {
    firstNavigationDone: Promise.resolve(),
    resetFirstNavigation() {
      this.firstNavigationDone = new Promise<void>((resolve) => { markFirstNavigationDone = resolve; });
    },
    finishFirstNavigation: () => markFirstNavigationDone(),
    isReady() { return this.firstNavigationDone; },
    resolve: () => ({ meta: {} }),
  };
});
const fakeApi = vi.hoisted(() => ({ helloWorld: vi.fn(), getActiveDeals: vi.fn() }));

vi.mock("./router", () => ({ default: fakeRouter }));
vi.mock("./api", () => ({
  default: fakeApi,
  apiClient: { interceptors: { request: { use: vi.fn() }, response: { use: vi.fn() } } },
}));
vi.mock("./api/auth", () => ({ authApi: {} }));
vi.mock("./components/shell/AppShell.vue", () => ({ default: { template: "<div><slot /></div>" } }));
vi.mock("./components/shell/AppKeyGate.vue", () => ({ default: { template: "<div />" } }));
vi.mock("./components/shell/SecurityBar.vue", () => ({ default: { template: "<div />" } }));
vi.mock("./components/liquidity/LiquidityTimelineChangePrompt.vue", () => ({ default: { template: "<div />" } }));
vi.mock("./components/liquidity/LiquidityRowsChangedNotice.vue", () => ({ default: { template: "<div />" } }));

import App from "./App.vue";
import { useAuthStore } from "./stores/authStore";

let wrapper: VueWrapper | null = null;

function mountApp() {
  wrapper = mount(App, { global: { stubs: { RouterView: true, UiTransition: true } } });
}

describe("App.vue: deals fetch on page load", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    fakeRouter.resetFirstNavigation();
    fakeApi.helloWorld.mockReset().mockResolvedValue({});
    fakeApi.getActiveDeals.mockReset().mockResolvedValue([]);
  });

  afterEach(() => {
    wrapper?.unmount();
    wrapper = null;
  });

  it("does not ask for the deals until the first navigation (and its session load) has finished", async () => {
    mountApp();
    await flushPromises();
    expect(fakeApi.getActiveDeals).not.toHaveBeenCalled();

    useAuthStore().status = "trusted";
    fakeRouter.finishFirstNavigation();
    await flushPromises();
    expect(fakeApi.getActiveDeals).toHaveBeenCalledTimes(1);
  });

  it("waits while the visitor is sent to sign in, then fetches the deals once the session is trusted", async () => {
    const authStore = useAuthStore();
    authStore.status = "anon";
    mountApp();
    fakeRouter.finishFirstNavigation();
    await flushPromises();
    expect(fakeApi.getActiveDeals).not.toHaveBeenCalled();

    authStore.status = "trusted";
    await flushPromises();
    expect(fakeApi.getActiveDeals).toHaveBeenCalledTimes(1);

    authStore.status = "anon";
    await flushPromises();
    authStore.status = "trusted";
    await flushPromises();
    expect(fakeApi.getActiveDeals).toHaveBeenCalledTimes(1);
  });

  it("fetches right away after the first navigation when sessions are not enforced (auth off)", async () => {
    useAuthStore().status = "off";
    mountApp();
    fakeRouter.finishFirstNavigation();
    await flushPromises();
    expect(fakeApi.getActiveDeals).toHaveBeenCalledTimes(1);
  });
});
