<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useAuthStore } from "../stores/authStore";

/**
 * Passkey sign-in. Shown only when the API enforces sessions; the button
 * triggers Face ID / Touch ID (or a security key) through WebAuthn. After a
 * successful assertion the router continues to `?next` or the dashboard.
 */
const auth = useAuthStore();
const route = useRoute();
const router = useRouter();
const busy = ref(false);

const nextPath = () => {
  const next = typeof route.query.next === "string" ? route.query.next : "/";
  return next.startsWith("/") && !next.startsWith("//") ? next : "/";
};

async function signIn() {
  busy.value = true;
  try {
    const status = await auth.login();
    await router.replace(status === "pending" ? "/pending" : nextPath());
  } catch {
    /* auth.error carries the message */
  } finally {
    busy.value = false;
  }
}

onMounted(async () => {
  if (auth.status === "unknown") await auth.load();
  if (auth.status === "trusted") await router.replace(nextPath());
  else if (auth.status === "pending") await router.replace("/pending");
});
</script>

<template>
  <section class="mx-auto flex min-h-[60vh] max-w-md flex-col justify-center gap-6 p-6" data-testid="login.page">
    <div>
      <p class="text-xs uppercase tracking-wide text-fg-muted">BigWhales</p>
      <h1 class="text-2xl font-semibold text-fg">Sign in</h1>
      <p class="mt-2 text-sm text-fg-muted">
        This site is private. Sign in with the passkey saved on this device: Face ID, Touch ID or your security key.
      </p>
    </div>

    <p v-if="!auth.supportsPasskeys" class="rounded-ctl border border-negative/40 bg-negative/10 p-3 text-sm text-fg" data-testid="login.unsupported">
      This browser does not support passkeys. Use Safari, Chrome or Edge on a recent OS.
    </p>

    <button
      type="button"
      data-testid="login.passkey"
      :disabled="busy || !auth.supportsPasskeys"
      class="w-full rounded-ctl bg-primary px-4 py-3 font-medium text-primary-fg disabled:opacity-60"
      @click="signIn"
    >
      <i class="pi pi-lock mr-2" aria-hidden="true"></i>{{ busy ? "Waiting for your passkey…" : "Sign in with a passkey" }}
    </button>

    <p v-if="auth.error" class="text-sm text-negative" role="alert" data-testid="login.error">{{ auth.error }}</p>

    <p class="text-xs text-fg-muted">
      No passkey on this device yet? Ask the other owner for an enrollment link, or run
      <code>python manage.py enroll</code> on the server.
    </p>
  </section>
</template>
