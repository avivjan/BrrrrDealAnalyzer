<script setup lang="ts">
/**
 * One row of the command palette's listbox: icon, label, an optional hint on
 * the right. `role="option"` with `aria-selected` mirroring `active`, and an
 * `id` the palette's combobox can point `aria-activedescendant` at.
 *
 * It renders no behaviour: the palette owns the click and the keyboard, and
 * reaches this row through the attrs it passes (`@click`, `@mousemove`).
 */
import { computed, useAttrs } from "vue";

import { cn } from "../../design/cn";

const props = withDefaults(
  defineProps<{
    id: string;
    label: string;
    hint?: string;
    /** A primeicons class. Decorative. */
    icon?: string;
    active?: boolean;
  }>(),
  { hint: undefined, icon: undefined, active: false },
);

defineOptions({ inheritAttrs: false });

const attrs = useAttrs();

function passthrough() {
  const rest: Record<string, unknown> = { ...attrs };
  delete rest.class;
  return rest;
}

const rootClass = computed(() =>
  cn(
    "flex min-h-11 cursor-pointer items-center gap-3 rounded-ctl px-3 py-2 text-sm transition-colors duration-fast",
    props.active ? "bg-primary/12 text-fg shadow-glow-primary" : "text-fg-muted",
    attrs.class as string,
  ),
);
</script>

<template>
  <div
    :id="`cmd-${id}`"
    data-ui="command-item"
    role="option"
    :aria-selected="active"
    :data-active="active || undefined"
    :class="rootClass"
    v-bind="passthrough()"
  >
    <i v-if="icon" :class="cn(icon, 'w-4 text-center text-sm', active ? 'text-primary' : 'text-fg-muted')" aria-hidden="true" />
    <span data-part="label" class="flex-1 truncate text-fg">{{ label }}</span>
    <span v-if="hint" data-part="hint" class="numeric shrink-0 text-xs text-fg-muted">{{ hint }}</span>
    <slot />
  </div>
</template>
