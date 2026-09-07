<script setup lang="ts">
import { ref } from "vue";
import { appKeyRequired, storeAppKey } from "../../auth/appKey";

/**
 * Shown only when the backend has refused a request with 401
 * `app_key_required`. Saves the key and reloads so every store refetches with
 * it. Nothing here renders while the gate is off, so the page is unchanged.
 */
const draft = ref("");

function submit() {
  if (!draft.value.trim()) return;
  storeAppKey(draft.value);
  window.location.reload();
}
</script>

<template>
  <div
    v-if="appKeyRequired"
    data-testid="app.key-gate"
    role="dialog"
    aria-modal="true"
    aria-labelledby="app-key-title"
    class="fixed inset-0 z-[1000] flex items-center justify-center bg-bg/90 p-4"
  >
    <form class="w-full max-w-sm space-y-4 rounded-card border border-line bg-surface p-6 shadow-lg" @submit.prevent="submit">
      <h2 id="app-key-title" class="text-lg font-semibold text-fg">Access key</h2>
      <p class="text-sm text-fg-muted">This site is private. Enter the access key once; it stays in this browser.</p>
      <input
        v-model="draft"
        data-testid="app.key-input"
        type="password"
        autocomplete="off"
        class="w-full rounded-ctl border border-line bg-transparent px-3 py-2 text-fg outline-none focus:border-primary"
        placeholder="Access key"
      />
      <button
        type="submit"
        data-testid="app.key-submit"
        class="w-full rounded-ctl bg-primary px-3 py-2 font-medium text-primary-fg"
      >
        Continue
      </button>
    </form>
  </div>
</template>
