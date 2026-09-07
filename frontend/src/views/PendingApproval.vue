<script setup lang="ts">
import { onBeforeUnmount, onMounted } from "vue";
import { useRouter } from "vue-router";
import { useAuthStore } from "../stores/authStore";

/**
 * A signed-in session on a browser that has not been approved yet
 * (DEVICE_POLICY=enforce). Polls until a trusted device approves it.
 */
const auth = useAuthStore();
const router = useRouter();
let timer: ReturnType<typeof setInterval> | undefined;

async function poll() {
  const status = await auth.refreshStatus();
  if (status === "trusted" || status === "off") await router.replace("/");
  else if (status === "anon") await router.replace("/login");
}

onMounted(() => {
  poll();
  timer = setInterval(poll, 10_000);
});
onBeforeUnmount(() => {
  if (timer) clearInterval(timer);
});
</script>

<template>
  <section class="mx-auto flex min-h-[60vh] max-w-md flex-col justify-center gap-6 p-6" data-testid="pending.page">
    <div>
      <p class="text-xs uppercase tracking-wide text-fg-muted">BigWhales</p>
      <h1 class="text-2xl font-semibold text-fg">Waiting for approval</h1>
      <p class="mt-2 text-sm text-fg-muted">
        You are signed in, but this browser is new. Approve it from a device that is already trusted
        (Settings → Devices), and this page will continue on its own.
      </p>
    </div>
    <p class="text-xs text-fg-muted" data-testid="pending.device">
      Device id: <code>{{ auth.session?.device_id }}</code>
    </p>
    <button type="button" class="text-sm text-primary underline-offset-2 hover:underline" data-testid="pending.logout" @click="auth.logout().then(() => router.replace('/login'))">
      Sign out
    </button>
  </section>
</template>
