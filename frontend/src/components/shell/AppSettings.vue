<script setup lang="ts">
/**
 * Settings → Appearance. Look, Mode and Motion, saved automatically, per
 * browser. The drawer reads and writes `src/design/theme.ts`'s singletons
 * directly: there is no form state to submit and no request leaves the page.
 * A polite live region says what changed, for anyone not looking at the card.
 */
import { computed, ref, watch } from "vue";

import { LOOKS } from "../../design/looks";
import {
  look,
  motionChoice,
  resolvedTheme,
  setLook,
  setMotion,
  setTheme,
  themeChoice,
  type MotionChoice,
  type ThemeChoice,
} from "../../design/theme";
import LookPicker from "./LookPicker.vue";

defineProps<{ open: boolean }>();
const emit = defineEmits<{ close: [] }>();

const MODE_OPTIONS = [
  { value: "light", label: "Light", icon: "pi pi-sun" },
  { value: "dark", label: "Dark", icon: "pi pi-moon" },
  { value: "system", label: "System", icon: "pi pi-desktop" },
];

const MOTION_OPTIONS = [
  { value: "full", label: "Full", icon: "pi pi-play" },
  { value: "reduced", label: "Reduced", icon: "pi pi-pause" },
];

const lookName = computed(() => LOOKS.find((entry) => entry.id === look.value)?.name ?? look.value);
const modeName = computed(() => (themeChoice.value === "system" ? `System (${resolvedTheme.value})` : resolvedTheme.value === "dark" ? "Dark" : "Light"));

/** Spoken after a change; empty on open so the drawer's own title is what is read first. */
const announcement = ref("");
watch([look, themeChoice, resolvedTheme, motionChoice], () => {
  announcement.value = `Look: ${lookName.value} · Mode: ${modeName.value} · Motion: ${motionChoice.value === "reduced" ? "Reduced" : "Full"}`;
});
</script>

<template>
  <UiDrawer :open="open" side="right" size="md" data-testid="shell.settings" @close="emit('close')">
    <template #header>Appearance</template>

    <div class="flex flex-col gap-6">
      <section class="flex flex-col gap-3">
        <div>
          <h3 class="text-sm font-semibold text-fg">Look</h3>
          <p class="text-xs text-fg-muted">Colours, type, depth and tempo. Every screen follows the look you pick.</p>
        </div>
        <LookPicker :model-value="look" :mode="resolvedTheme" @update:model-value="setLook($event)" />
      </section>

      <section class="flex flex-col gap-3">
        <div>
          <h3 class="text-sm font-semibold text-fg">Mode</h3>
          <p class="text-xs text-fg-muted">System follows your device's setting.</p>
        </div>
        <UiSegmented
          data-testid="shell.mode"
          :options="MODE_OPTIONS"
          :model-value="themeChoice"
          ariaLabel="Mode"
          block
          @update:model-value="setTheme($event as ThemeChoice)"
        />
      </section>

      <section class="flex flex-col gap-3">
        <div>
          <h3 class="text-sm font-semibold text-fg">Motion</h3>
          <p class="text-xs text-fg-muted">Reduced turns off entrances and ambient movement here, whatever the device says.</p>
        </div>
        <UiSegmented
          data-testid="shell.motion"
          :options="MOTION_OPTIONS"
          :model-value="motionChoice"
          ariaLabel="Motion"
          block
          @update:model-value="setMotion($event as MotionChoice)"
        />
      </section>

      <p role="status" aria-live="polite" class="sr-only">{{ announcement }}</p>
    </div>

    <template #footer>
      Saved automatically in this browser. Each browser keeps its own choice; a private window starts from the default.
    </template>
  </UiDrawer>
</template>
