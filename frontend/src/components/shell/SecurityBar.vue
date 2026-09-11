<script setup lang="ts">
import { computed } from "vue";
import { useAuthStore } from "../../stores/authStore";

/**
 * A one-line strip above every page, only while a session exists: who is
 * signed in and the way to the devices dashboard. With `AUTH_MODE=off` there
 * is no session, so nothing renders and every page is exactly as before.
 */
const auth = useAuthStore();
const shown = computed(() => auth.status === "trusted" || auth.status === "pending");
</script>

<template>
  <div
    v-if="shown"
    class="flex items-center justify-between gap-3 border-b border-line bg-surface px-4 py-1.5 text-xs text-fg-muted"
    data-testid="security.bar"
  >
    <span>Signed in as <strong class="text-fg">{{ auth.user?.display_name }}</strong></span>
    <RouterLink to="/settings/devices" class="text-primary underline-offset-2 hover:underline" data-testid="security.devices-link">
      <i class="pi pi-shield mr-1" aria-hidden="true"></i>Devices &amp; passkeys
    </RouterLink>
  </div>
</template>
