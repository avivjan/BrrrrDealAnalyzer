<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { authApi, type CredentialInfo, type DeviceInfo, type SessionInfo } from "../api/auth";
import { useAuthStore } from "../stores/authStore";

/**
 * Devices, sessions and passkeys (SECURITY_PLAN.md §3.4). Any trusted owner
 * approves or revokes any device; sessions and passkeys are the caller's own.
 * Approve, revoke and passkey removal trigger a fresh passkey prompt through
 * the API's `reauth_required` answer (handled by the axios interceptor).
 */
const auth = useAuthStore();
const route = useRoute();
const router = useRouter();

const devices = ref<DeviceInfo[]>([]);
const sessions = ref<SessionInfo[]>([]);
const credentials = ref<CredentialInfo[]>([]);
const error = ref<string | null>(null);
const busy = ref<string | null>(null);
const renaming = ref<{ id: string; label: string } | null>(null);
const enrollLink = ref<string | null>(null);

const pending = computed(() => devices.value.filter((d) => d.status === "pending"));

function describe(e: any): string {
  return e?.response?.data?.detail || e?.message || "Something went wrong";
}

function when(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return isNaN(d.getTime()) ? iso : d.toLocaleString();
}

async function load() {
  error.value = null;
  try {
    [devices.value, sessions.value, credentials.value] = await Promise.all([authApi.devices(), authApi.sessions(), authApi.credentials()]);
  } catch (e) {
    error.value = describe(e);
  }
}

async function run(key: string, action: () => Promise<unknown>) {
  busy.value = key;
  error.value = null;
  try {
    await action();
    await load();
  } catch (e) {
    error.value = describe(e);
  } finally {
    busy.value = null;
  }
}

const approve = (d: DeviceInfo) => run(`approve:${d.id}`, () => authApi.approveDevice(d.id));
const revoke = (d: DeviceInfo) => {
  if (!window.confirm(`Revoke "${d.label}"? Every session on it ends now.`)) return;
  return run(`revoke:${d.id}`, () => authApi.revokeDevice(d.id));
};
const saveRename = () => {
  const r = renaming.value;
  if (!r) return;
  return run(`rename:${r.id}`, async () => {
    await authApi.renameDevice(r.id, r.label);
    renaming.value = null;
  });
};
const endSession = (s: SessionInfo) =>
  run(`end:${s.id}`, async () => {
    await authApi.endSession(s.id);
    if (s.is_current) {
      await auth.logout();
      await router.replace("/login");
    }
  });
const endOthers = () => run("end-others", () => authApi.endOtherSessions());
const removeCredential = (c: CredentialInfo) => {
  if (!window.confirm(`Remove the passkey "${c.label}"?`)) return;
  return run(`cred:${c.id}`, () => authApi.deleteCredential(c.id));
};
const addPasskeyLink = () =>
  run("enroll-link", async () => {
    const { token } = await authApi.enrollmentToken();
    enrollLink.value = `${window.location.origin}/enroll?token=${encodeURIComponent(token)}`;
  });

onMounted(async () => {
  if (auth.status === "unknown") await auth.load();
  if (auth.status === "pending") {
    await router.replace("/pending");
    return;
  }
  if (auth.status !== "trusted") {
    await router.replace({ name: "login", query: { next: route.fullPath } });
    return;
  }
  await load();
});
</script>

<template>
  <section class="mx-auto flex max-w-3xl flex-col gap-8 p-6" data-testid="devices.page">
    <div>
      <p class="text-xs uppercase tracking-wide text-fg-muted">Security</p>
      <h1 class="text-2xl font-semibold text-fg">Devices &amp; passkeys</h1>
    </div>

    <p v-if="error" class="rounded-ctl border border-negative/40 bg-negative/10 p-3 text-sm text-fg" role="alert" data-testid="devices.error">{{ error }}</p>

    <p v-if="pending.length" class="rounded-ctl border border-primary/40 bg-primary/10 p-3 text-sm text-fg" data-testid="devices.pending-banner">
      {{ pending.length === 1 ? "A new device is waiting for approval." : `${pending.length} new devices are waiting for approval.` }}
      Approve it only if you recognise it.
    </p>

    <!-- Devices -->
    <div class="flex flex-col gap-3">
      <h2 class="text-sm font-semibold text-fg">Devices</h2>
      <ul class="flex flex-col gap-2" role="list">
        <li v-for="d in devices" :key="d.id" class="flex flex-col gap-2 rounded-ctl border border-line bg-surface p-3 text-sm sm:flex-row sm:items-center sm:justify-between" data-testid="devices.row" :data-status="d.status" :data-kind="d.kind">
          <div class="min-w-0">
            <div class="flex flex-wrap items-center gap-2">
              <template v-if="renaming?.id === d.id">
                <input v-model="renaming!.label" class="rounded-ctl border border-line bg-page px-2 py-1 text-sm text-fg" maxlength="200" data-testid="devices.rename-input" @keyup.enter="saveRename" />
                <button type="button" class="text-primary" data-testid="devices.rename-save" @click="saveRename">Save</button>
                <button type="button" class="text-fg-muted" @click="renaming = null">Cancel</button>
              </template>
              <template v-else>
                <strong class="text-fg" data-testid="devices.label">{{ d.label }}</strong>
                <button type="button" class="text-xs text-fg-muted underline-offset-2 hover:underline" data-testid="devices.rename" @click="renaming = { id: d.id, label: d.label }">Rename</button>
              </template>
              <span class="rounded-full border border-line px-2 py-0.5 text-[11px] uppercase tracking-wide text-fg-muted">{{ d.kind === "mcp" ? "Claude connector" : d.platform || "Browser" }}</span>
              <span v-if="d.is_current" class="text-[11px] uppercase tracking-wide text-primary">This device</span>
              <span v-if="d.status !== 'trusted'" class="text-[11px] uppercase tracking-wide" :class="d.status === 'pending' ? 'text-warning' : 'text-negative'" data-testid="devices.status">{{ d.status }}</span>
            </div>
            <p class="text-xs text-fg-muted">
              {{ d.user_display_name }} · first seen {{ when(d.first_seen_at) }} · last seen {{ when(d.last_seen_at) }}<span v-if="d.last_ip"> · {{ d.last_ip }}</span>
            </p>
          </div>
          <div class="flex shrink-0 gap-2">
            <button v-if="d.status === 'pending'" type="button" class="rounded-ctl bg-primary px-3 py-1.5 text-primary-fg disabled:opacity-60" :disabled="busy !== null" data-testid="devices.approve" @click="approve(d)">Approve</button>
            <button v-if="d.status !== 'revoked' && !d.is_current" type="button" class="rounded-ctl border border-negative/40 px-3 py-1.5 text-negative disabled:opacity-60" :disabled="busy !== null" data-testid="devices.revoke" @click="revoke(d)">Revoke</button>
          </div>
        </li>
      </ul>
    </div>

    <!-- Sessions -->
    <div class="flex flex-col gap-3">
      <div class="flex items-center justify-between">
        <h2 class="text-sm font-semibold text-fg">Your sessions</h2>
        <button type="button" class="text-xs text-negative underline-offset-2 hover:underline disabled:opacity-60" :disabled="busy !== null || sessions.length < 2" data-testid="sessions.end-others" @click="endOthers">End all other sessions</button>
      </div>
      <ul class="flex flex-col gap-2" role="list">
        <li v-for="s in sessions" :key="s.id" class="flex items-center justify-between gap-3 rounded-ctl border border-line bg-surface p-3 text-sm" data-testid="sessions.row">
          <div>
            <strong class="text-fg">{{ s.device_label }}</strong>
            <span v-if="s.is_current" class="ml-2 text-[11px] uppercase tracking-wide text-primary">Current</span>
            <p class="text-xs text-fg-muted">started {{ when(s.created_at) }} · last seen {{ when(s.last_seen_at) }}<span v-if="s.ip"> · {{ s.ip }}</span></p>
          </div>
          <button type="button" class="text-xs text-negative underline-offset-2 hover:underline disabled:opacity-60" :disabled="busy !== null" data-testid="sessions.end" @click="endSession(s)">{{ s.is_current ? "Sign out" : "End" }}</button>
        </li>
      </ul>
    </div>

    <!-- Passkeys -->
    <div class="flex flex-col gap-3">
      <div class="flex items-center justify-between">
        <h2 class="text-sm font-semibold text-fg">Your passkeys</h2>
        <button type="button" class="text-xs text-primary underline-offset-2 hover:underline disabled:opacity-60" :disabled="busy !== null" data-testid="passkeys.add-link" @click="addPasskeyLink">Add a passkey on another device</button>
      </div>
      <p v-if="enrollLink" class="rounded-ctl border border-line bg-surface p-3 text-xs text-fg" data-testid="passkeys.link">
        Open this link on the other device within 15 minutes (it works once):<br />
        <code class="break-all">{{ enrollLink }}</code>
      </p>
      <ul class="flex flex-col gap-2" role="list">
        <li v-for="c in credentials" :key="c.id" class="flex items-center justify-between gap-3 rounded-ctl border border-line bg-surface p-3 text-sm" data-testid="passkeys.row">
          <div>
            <strong class="text-fg">{{ c.label }}</strong>
            <span v-if="c.backup_state" class="ml-2 text-[11px] uppercase tracking-wide text-fg-muted">Synced</span>
            <p class="text-xs text-fg-muted">added {{ when(c.created_at) }} · last used {{ when(c.last_used_at) }}</p>
          </div>
          <button type="button" class="text-xs text-negative underline-offset-2 hover:underline disabled:opacity-60" :disabled="busy !== null || credentials.length < 2" :title="credentials.length < 2 ? 'The last passkey cannot be removed' : ''" data-testid="passkeys.delete" @click="removeCredential(c)">Remove</button>
        </li>
      </ul>
    </div>
  </section>
</template>
