import { beforeEach, describe, expect, it, vi } from "vitest";
import { createPinia, setActivePinia } from "pinia";

const api = vi.hoisted(() => ({
  config: vi.fn(),
  me: vi.fn(),
  refresh: vi.fn(),
  logout: vi.fn(),
  loginOptions: vi.fn(),
  loginVerify: vi.fn(),
  registerOptions: vi.fn(),
  registerVerify: vi.fn(),
  reauthOptions: vi.fn(),
  reauthVerify: vi.fn(),
  enrollmentToken: vi.fn(),
}));
const webauthn = vi.hoisted(() => ({
  startAuthentication: vi.fn(),
  startRegistration: vi.fn(),
  browserSupportsWebAuthn: vi.fn(() => true),
}));

vi.mock("../api/auth", () => ({ authApi: api }));
vi.mock("@simplewebauthn/browser", () => webauthn);

import { useAuthStore } from "./authStore";

const SESSION = {
  status: "ok" as const,
  user: { id: "u1", username: "aviv", display_name: "Aviv", reps_user: "Aviv2026", role: "owner" },
  device_id: "d1",
  device_status: "trusted",
  auth_mode: "enforce" as const,
  device_policy: "off" as const,
};

describe("authStore", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    for (const fn of Object.values(api)) (fn as ReturnType<typeof vi.fn>).mockReset();
    webauthn.startAuthentication.mockReset();
    webauthn.startRegistration.mockReset();
  });

  it("is `off` when the API does not enforce sessions, even when /auth/me fails", async () => {
    api.config.mockResolvedValue({ auth_mode: "off", device_policy: "off", rp_id: "" });
    api.me.mockRejectedValue(new Error("401"));
    const store = useAuthStore();
    expect(await store.load()).toBe("off");
    expect(store.enforced).toBe(false);
  });

  it("is `off` when /auth/config does not exist (an older backend)", async () => {
    api.config.mockRejectedValue(new Error("404"));
    api.me.mockRejectedValue(new Error("401"));
    expect(await useAuthStore().load()).toBe("off");
  });

  it("is `trusted` with a live session under enforce", async () => {
    api.config.mockResolvedValue({ auth_mode: "enforce", device_policy: "off", rp_id: "localhost" });
    api.me.mockResolvedValue(SESSION);
    const store = useAuthStore();
    expect(await store.load()).toBe("trusted");
    expect(store.user?.username).toBe("aviv");
  });

  it("refreshes once before giving up, then is `anon`", async () => {
    api.config.mockResolvedValue({ auth_mode: "enforce", device_policy: "off", rp_id: "localhost" });
    api.me.mockRejectedValue(new Error("401"));
    api.refresh.mockRejectedValue(new Error("401"));
    expect(await useAuthStore().load()).toBe("anon");
    expect(api.refresh).toHaveBeenCalledTimes(1);
  });

  it("is `pending` when the device awaits approval", async () => {
    api.config.mockResolvedValue({ auth_mode: "enforce", device_policy: "enforce", rp_id: "localhost" });
    api.me.mockResolvedValue({ ...SESSION, status: "pending_approval", device_status: "pending" });
    expect(await useAuthStore().load()).toBe("pending");
  });

  it("login runs the ceremony and stores the session", async () => {
    api.loginOptions.mockResolvedValue({ challenge_id: "c1", options: JSON.stringify({ challenge: "abc" }) });
    webauthn.startAuthentication.mockResolvedValue({ id: "cred" });
    api.loginVerify.mockResolvedValue(SESSION);
    const store = useAuthStore();
    expect(await store.login()).toBe("trusted");
    expect(webauthn.startAuthentication).toHaveBeenCalledWith({ optionsJSON: { challenge: "abc" } });
    expect(api.loginVerify).toHaveBeenCalledWith("c1", { id: "cred" });
  });

  it("login surfaces the API's detail as the error", async () => {
    api.loginOptions.mockResolvedValue({ challenge_id: "c1", options: "{}" });
    webauthn.startAuthentication.mockResolvedValue({ id: "cred" });
    api.loginVerify.mockRejectedValue({ response: { data: { detail: "passkey could not be verified" } } });
    const store = useAuthStore();
    await expect(store.login()).rejects.toBeTruthy();
    expect(store.error).toBe("passkey could not be verified");
  });

  it("enroll runs the registration ceremony with the token and label", async () => {
    api.registerOptions.mockResolvedValue({ challenge_id: "c2", options: "{}", username: "aviv" });
    webauthn.startRegistration.mockResolvedValue({ id: "new" });
    api.registerVerify.mockResolvedValue(SESSION);
    expect(await useAuthStore().enroll("tok", "Mac")).toBe("trusted");
    expect(api.registerVerify).toHaveBeenCalledWith("tok", "c2", { id: "new" }, "Mac");
  });

  it("logout clears the session and returns to anon under enforce", async () => {
    api.config.mockResolvedValue({ auth_mode: "enforce", device_policy: "off", rp_id: "localhost" });
    api.me.mockResolvedValue(SESSION);
    api.logout.mockResolvedValue(undefined);
    const store = useAuthStore();
    await store.load();
    await store.logout();
    expect(store.status).toBe("anon");
    expect(store.user).toBeNull();
  });
});
