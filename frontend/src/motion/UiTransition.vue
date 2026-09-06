<script setup lang="ts">
/**
 * `<UiTransition preset="…">` — the only way a frozen view template animates.
 *
 * Phase 4 may not add a line to any view's `<script setup>`, so a view cannot
 * import a preset or write a hook. It writes one wrapper element with one
 * `preset` attribute instead, and `main.ts` has already registered this
 * component globally.
 *
 * `:css="false"` tells Vue there are no transition classes to wait for, so the
 * hooks below own the timing completely. `mode` is never set, in this file or
 * by a caller: `mode="out-in"` would hold the entering element back until the
 * leaving one finished, which turns decoration into latency in front of real
 * content.
 */
import { computed } from 'vue';

import { presets, transitionHooks, type PresetName } from './presets';

const props = withDefaults(defineProps<{ preset: PresetName; appear?: boolean }>(), {
  appear: false,
});

/**
 * Bound with `v-bind` rather than `v-on` so the keys reach Vue exactly as
 * written (see `transitionHooks`). An enter-only preset contributes no
 * `onLeave`, and Vue then removes the element itself with no hook involved.
 */
const hooks = computed(() => transitionHooks(presets[props.preset]));
</script>

<template>
  <Transition v-bind="hooks" :css="false" :appear="appear">
    <slot />
  </Transition>
</template>
