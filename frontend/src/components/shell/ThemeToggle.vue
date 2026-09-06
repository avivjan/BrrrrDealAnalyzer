<script setup lang="ts">
/**
 * Light ↔ dark. Names its destination, not its state, so a screen reader hears
 * what the press will do. The full three-way choice (incl. "system") lives in
 * Settings → Appearance; this is the shortcut.
 */
import { computed } from "vue";

import { resolvedTheme, toggleTheme } from "../../design/theme";

const label = computed(() => (resolvedTheme.value === "dark" ? "Switch to light mode" : "Switch to dark mode"));
</script>

<template>
  <UiIconButton data-testid="shell.theme-toggle" size="md" :label="label" @click="toggleTheme()">
    <i :class="resolvedTheme === 'dark' ? 'pi pi-sun' : 'pi pi-moon'" aria-hidden="true" />
  </UiIconButton>
</template>
