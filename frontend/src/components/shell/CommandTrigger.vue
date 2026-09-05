<script setup lang="ts">
/**
 * "Search… ⌘K". Looks like a search field, is a button: the palette it opens
 * is the search. The click is the parent's.
 */
import { computed } from "vue";

const isMac = computed(() => {
  if (typeof navigator === "undefined") return false;
  const modern = (navigator as Navigator & { userAgentData?: { platform?: string } }).userAgentData?.platform;
  return /mac|iphone|ipad/i.test(modern ?? navigator.userAgent);
});
</script>

<template>
  <button
    type="button"
    data-testid="shell.command-trigger"
    class="hidden min-h-9 items-center gap-2 rounded-ctl border-ui border-line bg-surface-2 px-3 text-sm text-fg-muted transition-[color,border-color,box-shadow] duration-fast ease-standard hover:border-primary/40 hover:text-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring md:inline-flex md:min-w-[14rem]"
  >
    <i class="pi pi-search text-xs" aria-hidden="true" />
    <span class="flex-1 text-left">Search or jump to…</span>
    <kbd class="numeric rounded-[4px] border-ui border-line bg-surface px-1.5 py-0.5 text-[10px] text-fg-muted">{{ isMac ? "⌘K" : "Ctrl K" }}</kbd>
  </button>
</template>
