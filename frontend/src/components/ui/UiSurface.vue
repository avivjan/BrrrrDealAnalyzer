<script setup lang="ts">
/**
 * A plain panel at one of three elevation tiers. The most-used shape in the
 * v2 shell and views: it replaces the `bg-white rounded-lg shadow` chains.
 *
 * Tier 1 is the base surface with a hairline; tier 2 and 3 step up the surface
 * colour and the shadow, so nested panels read as nested. The look decides
 * what "hairline", "shadow" and "radius" mean — a brutalist look renders the
 * same tiers as 2 px borders and hard offsets.
 */
import { computed, useAttrs } from "vue";

import { cn } from "../../design/cn";

type Level = 1 | 2 | 3;

const props = withDefaults(
  defineProps<{
    level?: Level;
    as?: string;
    /** Lift on hover and press feedback. Purely visual — the click is the parent's. */
    interactive?: boolean;
    padding?: "none" | "sm" | "md" | "lg";
  }>(),
  { level: 1, as: "div", interactive: false, padding: "md" },
);

defineOptions({ inheritAttrs: false });

const LEVELS: Record<Level, string> = {
  1: "bg-surface border-ui border-line shadow-1",
  2: "bg-surface-2 border-ui border-line shadow-2",
  3: "bg-surface-3 border-ui border-line shadow-3",
};

const PADDINGS = { none: "", sm: "p-3", md: "p-4", lg: "p-6" } as const;

const INTERACTIVE = "cursor-pointer hover:shadow-2 hover:-translate-y-px active:scale-[0.99]";

const attrs = useAttrs();

function passthrough() {
  const rest: Record<string, unknown> = { ...attrs };
  delete rest.class;
  return rest;
}

const rootClass = computed(() =>
  cn(
    "rounded-card transition-[box-shadow,transform,background-color,border-color] duration-fast ease-standard",
    LEVELS[props.level],
    PADDINGS[props.padding],
    props.interactive && INTERACTIVE,
    attrs.class as string,
  ),
);
</script>

<template>
  <component :is="as" data-ui="surface" :data-level="level" :class="rootClass" v-bind="passthrough()">
    <slot />
  </component>
</template>
