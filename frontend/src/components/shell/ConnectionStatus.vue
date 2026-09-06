<script setup lang="ts">
/**
 * The backend connection indicator, moved from a fixed dot in `App.vue` into
 * the topbar. Same hook, same role and live region, and — because the e2e
 * suite reads them — the same three strings, verbatim. The visible label on
 * `lg` gives the state a second channel besides colour.
 */
import { computed } from "vue";

import { useConnectionStore } from "../../stores/connectionStore";

const connectionStore = useConnectionStore();

const text = computed(() =>
  connectionStore.isChecking
    ? "Connecting to server..."
    : connectionStore.isConnected
      ? "Server Connected"
      : "Disconnected",
);

const busy = computed(() => connectionStore.isChecking || !connectionStore.isConnected);
</script>

<template>
  <span
    data-testid="app.status"
    role="status"
    aria-live="polite"
    :title="text"
    :aria-label="text"
    class="inline-flex min-h-8 items-center gap-2 rounded-full border-ui border-line bg-surface/70 px-2.5 text-xs text-fg-muted"
  >
    <span
      aria-hidden="true"
      class="h-2 w-2 shrink-0 rounded-full transition-colors duration-base ease-standard"
      :class="busy ? 'bg-negative animate-pulse' : 'bg-positive'"
    />
    <span class="hidden lg:inline" aria-hidden="true">{{ text }}</span>
  </span>
</template>
