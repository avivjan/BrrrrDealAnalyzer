import { ref } from "vue";

/**
 * Phase 0 stopgap: the shared app key (SECURITY_PLAN.md §4, step 0.2).
 *
 * The key never ships in the bundle. The user types it once; it lives in this
 * browser's localStorage and goes out as `X-App-Key` on every API request.
 * Passkey sessions replace it in Phase 2, at which point this file goes away.
 */
export const APP_KEY_HEADER = "X-App-Key";
export const APP_KEY_DETAIL = "app_key_required";
export const APP_KEY_STORAGE_KEY = "bw.appKey";

/** True once the backend has answered 401 `app_key_required`; the gate shows. */
export const appKeyRequired = ref(false);

export function readAppKey(): string | null {
  try {
    const value = localStorage.getItem(APP_KEY_STORAGE_KEY);
    return value && value.trim() ? value.trim() : null;
  } catch {
    return null;
  }
}

export function storeAppKey(value: string): void {
  try {
    localStorage.setItem(APP_KEY_STORAGE_KEY, value.trim());
  } catch {
    /* storage may be locked; the key is then asked for again next time */
  }
  appKeyRequired.value = false;
}
