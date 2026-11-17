import { beforeEach, describe, expect, it, vi } from "vitest";
import type { AxiosAdapter, InternalAxiosRequestConfig } from "axios";

/**
 * The 401 handler while the page is still loading the session: a data request
 * that hits an expired access cookie before `auth.load()` has finished must wait
 * for that load (which renews the session) and retry once -- never fail quietly,
 * and never start a second refresh of its own.
 */

const fakeAuthStore = vi.hoisted(() => ({
  status: "unknown" as string,
  enforced: false,
  load: vi.fn(),
  tryRefresh: vi.fn(),
}));
vi.mock("../stores/authStore", () => ({ useAuthStore: () => fakeAuthStore }));
vi.mock("../router", () => ({ default: { currentRoute: { value: { name: "home", fullPath: "/" } }, push: vi.fn() } }));

import { apiClient } from "./index";

function answerWithStatus(config: InternalAxiosRequestConfig, status: number, data: unknown) {
  if (status < 400) return Promise.resolve({ data, status, statusText: "", headers: {}, config });
  return Promise.reject(Object.assign(new Error(`Request failed with status code ${status}`), {
    config,
    response: { data, status, statusText: "", headers: {}, config },
    isAxiosError: true,
  }));
}

describe("401 on a data route while the session is still loading", () => {
  let isSessionRenewedOnTheServer = false;
  const fakeServerThatRejectsAnExpiredSession: AxiosAdapter = (config) =>
    isSessionRenewedOnTheServer
      ? answerWithStatus(config, 200, [{ id: "deal-1" }])
      : answerWithStatus(config, 401, { detail: "unauthenticated" });

  beforeEach(() => {
    isSessionRenewedOnTheServer = false;
    apiClient.defaults.adapter = fakeServerThatRejectsAnExpiredSession;
    fakeAuthStore.status = "unknown";
    fakeAuthStore.enforced = false;
    fakeAuthStore.load.mockReset();
    fakeAuthStore.tryRefresh.mockReset();
  });

  it("waits for auth.load() to renew the session, then retries the request once and returns its data", async () => {
    fakeAuthStore.load.mockImplementation(async () => {
      isSessionRenewedOnTheServer = true;
      fakeAuthStore.status = "trusted";
      fakeAuthStore.enforced = true;
      return "trusted";
    });

    const response = await apiClient.get("/active-deals");

    expect(response.data).toEqual([{ id: "deal-1" }]);
    expect(fakeAuthStore.load).toHaveBeenCalledTimes(1);
    expect(fakeAuthStore.tryRefresh).not.toHaveBeenCalled();
  });

  it("still rejects when sessions are not enforced (auth off): no retry loop", async () => {
    fakeAuthStore.load.mockImplementation(async () => {
      fakeAuthStore.status = "off";
      return "off";
    });

    await expect(apiClient.get("/active-deals")).rejects.toMatchObject({ response: { status: 401 } });
    expect(fakeAuthStore.load).toHaveBeenCalledTimes(1);
    expect(fakeAuthStore.tryRefresh).not.toHaveBeenCalled();
  });

  it("does not call auth.load() again once the session status is known", async () => {
    fakeAuthStore.status = "off";

    await expect(apiClient.get("/active-deals")).rejects.toMatchObject({ response: { status: 401 } });
    expect(fakeAuthStore.load).not.toHaveBeenCalled();
  });
});
