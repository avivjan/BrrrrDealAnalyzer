import { defineStore } from 'pinia';
import { computed, ref } from 'vue';
import { startAuthentication, startRegistration, browserSupportsWebAuthn } from '@simplewebauthn/browser';
import { authApi, type AuthConfig, type SessionStatus } from '../api/auth';

/**
 * Session state for the SPA. `status`:
 *   unknown   not loaded yet
 *   off       the API does not require a session (AUTH_MODE=off): no login UI
 *   anon      a session is required and there is none
 *   pending   logged in, but this browser awaits approval (DEVICE_POLICY)
 *   trusted   logged in on an approved browser
 */
export type AuthStatus = 'unknown' | 'off' | 'anon' | 'pending' | 'trusted';

function parseOptions(json: string): any {
  return JSON.parse(json);
}

export const useAuthStore = defineStore('auth', () => {
  const status = ref<AuthStatus>('unknown');
  const config = ref<AuthConfig | null>(null);
  const session = ref<SessionStatus | null>(null);
  const error = ref<string | null>(null);

  const user = computed(() => session.value?.user ?? null);
  const enforced = computed(() => (config.value?.auth_mode ?? 'off') === 'enforce');
  const supportsPasskeys = computed(() => browserSupportsWebAuthn());

  function applySession(next: SessionStatus) {
    session.value = next;
    status.value = next.status === 'ok' ? 'trusted' : 'pending';
  }

  /** Called once by the router guard before the first protected route. */
  async function load(): Promise<AuthStatus> {
    try {
      config.value = await authApi.config();
    } catch {
      // An old backend (no /auth/config) or a network error: behave as today.
      config.value = { auth_mode: 'off', device_policy: 'off', rp_id: '' };
    }
    if (config.value.auth_mode !== 'enforce') {
      // shadow and off: the API answers without a session; try to learn who we
      // are for the UI, but never block.
      try {
        applySession(await authApi.me());
      } catch {
        status.value = 'off';
      }
      if (status.value === 'unknown') status.value = 'off';
      return status.value;
    }
    try {
      applySession(await authApi.me());
    } catch {
      try {
        applySession(await authApi.refresh());
      } catch {
        session.value = null;
        status.value = 'anon';
      }
    }
    return status.value;
  }

  async function login(): Promise<AuthStatus> {
    error.value = null;
    try {
      const { challenge_id, options } = await authApi.loginOptions();
      const credential = await startAuthentication({ optionsJSON: parseOptions(options) });
      applySession(await authApi.loginVerify(challenge_id, credential));
    } catch (e: any) {
      error.value = e?.response?.data?.detail || e?.message || 'Sign-in failed';
      throw e;
    }
    return status.value;
  }

  async function enroll(token: string, label?: string): Promise<AuthStatus> {
    error.value = null;
    try {
      const { challenge_id, options } = await authApi.registerOptions(token);
      const credential = await startRegistration({ optionsJSON: parseOptions(options) });
      applySession(await authApi.registerVerify(token, challenge_id, credential, label));
    } catch (e: any) {
      error.value = e?.response?.data?.detail || e?.message || 'Enrollment failed';
      throw e;
    }
    return status.value;
  }

  async function reauth(): Promise<void> {
    const { challenge_id, options } = await authApi.reauthOptions();
    const credential = await startAuthentication({ optionsJSON: parseOptions(options) });
    applySession(await authApi.reauthVerify(challenge_id, credential));
  }

  async function refreshStatus(): Promise<AuthStatus> {
    try {
      applySession(await authApi.me());
    } catch {
      if (enforced.value) {
        session.value = null;
        status.value = 'anon';
      }
    }
    return status.value;
  }

  async function logout(): Promise<void> {
    try {
      await authApi.logout();
    } finally {
      session.value = null;
      status.value = enforced.value ? 'anon' : 'off';
    }
  }

  /** The 401 interceptor calls this: a session that just expired is refreshed once. */
  async function tryRefresh(): Promise<boolean> {
    if (!enforced.value) return false;
    try {
      applySession(await authApi.refresh());
      return true;
    } catch {
      session.value = null;
      status.value = 'anon';
      return false;
    }
  }

  return { status, config, session, user, error, enforced, supportsPasskeys, load, login, enroll, reauth, refreshStatus, logout, tryRefresh };
});
