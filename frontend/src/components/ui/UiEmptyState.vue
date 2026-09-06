<script setup lang="ts">
/**
 * The placeholder for a list with nothing in it.
 *
 * An empty region is ambiguous — nothing here, or something broken? — so this
 * always has room for a line of explanation and for the action that fills it.
 * The dashed border says "this box is meant to be empty" rather than "this box
 * failed to load"; a solid card would read as content.
 *
 * The icon is decorative and `aria-hidden`: it repeats what the title already
 * says, and an announced icon name is noise. All three pieces of copy are the
 * caller's.
 */
import { computed, useAttrs } from "vue";

import { cn } from "../../design/cn";

const props = withDefaults(defineProps<{ icon?: string }>(), { icon: undefined });

defineOptions({ inheritAttrs: false });

const BASE =
  "flex flex-col items-center justify-center rounded-card border border-dashed border-line " +
  "p-6 text-center text-fg-muted";

const attrs = useAttrs();

/**
 * Everything except `class`, which `rootClass` folds through `cn()` instead.
 * A plain function, not a `computed`: see `UiCard`.
 */
function passthrough() {
  const rest: Record<string, unknown> = { ...attrs };
  delete rest.class;
  return rest;
}

const rootClass = computed(() => cn(BASE, attrs.class as string));
const iconClass = computed(() => cn(props.icon, "mb-2 text-2xl text-fg-muted"));
</script>

<template>
  <div data-ui="empty-state" :class="rootClass" v-bind="passthrough()">
    <i v-if="icon" :class="iconClass" aria-hidden="true" />
    <p data-part="title" class="text-sm font-medium text-fg">
      <slot />
    </p>
    <p v-if="$slots.description" data-part="description" class="mt-1 max-w-prose text-sm">
      <slot name="description" />
    </p>
    <div v-if="$slots.actions" data-part="actions" class="mt-4">
      <slot name="actions" />
    </div>
  </div>
</template>
