<script setup lang="ts">
/**
 * A frosted panel. Depth through translucency and blur where the look allows
 * it; a look with `--blur-glass: 0px` renders an opaque surface-2 panel from
 * the very same class, so callers never branch on the look.
 *
 * The glass rule (MASTER.md): body text never sits directly on glass. A glass
 * panel is a *container* — its children are `UiSurface`s, `UiKpiCard`s, a nav
 * list — because text over a blurred, moving background cannot be held to a
 * contrast ratio.
 */
import { computed, useAttrs } from "vue";

import { cn } from "../../design/cn";

const props = withDefaults(
  defineProps<{
    intensity?: "low" | "high";
    as?: string;
    padding?: "none" | "sm" | "md" | "lg";
  }>(),
  { intensity: "low", as: "div", padding: "md" },
);

defineOptions({ inheritAttrs: false });

const PADDINGS = { none: "", sm: "p-3", md: "p-4", lg: "p-6" } as const;

const attrs = useAttrs();

function passthrough() {
  const rest: Record<string, unknown> = { ...attrs };
  delete rest.class;
  return rest;
}

const rootClass = computed(() =>
  cn(
    "glass rounded-panel",
    props.intensity === "high" ? "shadow-3" : "shadow-1",
    PADDINGS[props.padding],
    attrs.class as string,
  ),
);
</script>

<template>
  <component :is="as" data-ui="glass-panel" :data-intensity="intensity" :class="rootClass" v-bind="passthrough()">
    <slot />
  </component>
</template>
