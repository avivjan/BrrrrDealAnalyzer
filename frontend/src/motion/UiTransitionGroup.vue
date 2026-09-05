<script setup lang="ts">
/**
 * `<UiTransitionGroup preset="listItem" tag="ul">` — the list counterpart.
 *
 * Same contract as `UiTransition`: one wrapper element, `preset` and `tag`
 * attributes, no view script change. The extra thing a group does is *move* —
 * when the list reorders, Vue applies `move-class` to the items that shifted
 * and waits for their CSS transition. That one is CSS rather than GSAP because
 * Vue computes the FLIP offsets itself; `.ui-move` lives in `main.css`, next to
 * the reduced-motion neutraliser that flattens it.
 *
 * Never used inside `<VueDraggable>`: SortableJS owns that DOM, and two things
 * animating the same nodes fight.
 */
import { computed } from 'vue';

import { presets, transitionHooks, type PresetName } from './presets';

const props = withDefaults(defineProps<{ preset: PresetName; tag?: string }>(), {
  tag: 'div',
});

const hooks = computed(() => transitionHooks(presets[props.preset]));
</script>

<template>
  <TransitionGroup v-bind="hooks" :css="false" :tag="tag" move-class="ui-move">
    <slot />
  </TransitionGroup>
</template>
