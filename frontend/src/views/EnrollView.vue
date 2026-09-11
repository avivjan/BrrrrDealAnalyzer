<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useAuthStore } from "../stores/authStore";

/**
 * Enrollment: `/enroll?token=…` from `manage.py enroll` or from the other
 * owner's "add a passkey on another device" link. Creates the passkey on this
 * device and signs in.
 */
const auth = useAuthStore();
const route = useRoute();
const router = useRouter();
const busy = ref(false);
const label = ref("");
const token = ref("");

onMounted(() => {
  token.value = typeof route.query.token === "string" ? route.query.token : "";
  if (!label.value) label.value = defaultLabel();
});

function defaultLabel(): string {
  const ua = navigator.userAgent;
  if (/iPhone/.test(ua)) return "iPhone";
  if (/iPad/.test(ua)) return "iPad";
  if (/Mac OS/.test(ua)) return "Mac";
  if (/Android/.test(ua)) return "Android";
  if (/Windows/.test(ua)) return "Windows PC";
  return "This device";
}

async function createPasskey() {
  busy.value = true;
  try {
    const status = await auth.enroll(token.value, label.value.trim() || undefined);
    await router.replace(status === "pending" ? "/pending" : "/");
  } catch {
    /* auth.error carries the message */
  } finally {
    busy.value = false;
  }
}
</script>

<template>
  <section class="mx-auto flex min-h-[60vh] max-w-md flex-col justify-center gap-6 p-6" data-testid="enroll.page">
    <div>
      <p class="text-xs uppercase tracking-wide text-fg-muted">BigWhales</p>
      <h1 class="text-2xl font-semibold text-fg">Create your passkey</h1>
      <p class="mt-2 text-sm text-fg-muted">
        Your device will ask for Face ID, Touch ID or your security key. The passkey stays on your device (and in your
        iCloud Keychain if you use one); the site never sees a password.
      </p>
    </div>

    <p v-if="!token" class="rounded-ctl border border-negative/40 bg-negative/10 p-3 text-sm text-fg" data-testid="enroll.no-token">
      This link is missing its token. Ask for a new enrollment link.
    </p>

    <label class="flex flex-col gap-1 text-sm text-fg">
      <span class="text-xs font-medium text-fg-muted">Name this device</span>
      <input
        v-model="label"
        data-testid="enroll.label"
        class="rounded-ctl border border-line bg-transparent px-3 py-2 text-fg outline-none focus:border-primary"
        maxlength="200"
      />
    </label>

    <button
      type="button"
      data-testid="enroll.create"
      :disabled="busy || !token || !auth.supportsPasskeys"
      class="w-full rounded-ctl bg-primary px-4 py-3 font-medium text-primary-fg disabled:opacity-60"
      @click="createPasskey"
    >
      <i class="pi pi-key mr-2" aria-hidden="true"></i>{{ busy ? "Waiting for your device…" : "Create passkey and sign in" }}
    </button>

    <p v-if="auth.error" class="text-sm text-negative" role="alert" data-testid="enroll.error">{{ auth.error }}</p>
  </section>
</template>
