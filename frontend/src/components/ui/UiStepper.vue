<script setup lang="ts">
/**
 * The progress rail across a multi-step flow. A container, like `UiTabs`:
 * the steps stay in the view's own `v-for`, because which step is current is
 * behaviour this phase does not move.
 *
 * A child opts in by carrying `data-step="done" | "active" | "todo"`, and the
 * scoped block below styles it through `:slotted()` — colour, truncation and
 * the connector between steps. That is the only way a component can style
 * markup its parent owns, and it means a view adopting this changes an
 * enclosing tag and one attribute per step, nothing else.
 *
 * The columns come from `--steps` rather than a fixed class because the count
 * is a runtime value; equal `minmax(0, 1fr)` columns keep the rail the same
 * width whatever the labels say, and `minmax(0, …)` — not `1fr` alone — is
 * what lets a long label truncate instead of stretching its column.
 *
 * Long labels are ellipsised here; the view supplies the `title` attribute
 * that reveals the full text, since only the view has the string.
 */
import { computed, useAttrs } from "vue";

import { cn } from "../../design/cn";

const props = withDefaults(defineProps<{ count: number; compact?: boolean }>(), {
  compact: false,
});

defineOptions({ inheritAttrs: false });

const BASE =
  "ui-stepper grid list-none grid-cols-[repeat(var(--steps),minmax(0,1fr))] items-center gap-x-2";

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

const rootClass = computed(() =>
  cn(BASE, props.compact ? "text-xs" : "text-sm", attrs.class as string),
);
</script>

<template>
  <ol
    data-ui="stepper"
    role="list"
    :data-compact="compact || undefined"
    :class="rootClass"
    :style="{ '--steps': count }"
    v-bind="passthrough()"
  >
    <slot />
  </ol>
</template>

<style scoped>
/*
 * `:slotted()` is the one hook Vue gives a component onto markup its parent
 * renders. Everything here keys off `data-step`, so a list item without it is
 * left entirely alone.
 *
 * The step is a block, not a flex row, on purpose: `text-overflow: ellipsis`
 * only applies to inline content in a block container, and truncating a long
 * step name is the whole reason the columns are `minmax(0, 1fr)`.
 */
.ui-stepper :slotted([data-step]) {
  position: relative;
  min-width: 0;
  padding-left: 1.25rem;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
  color: rgb(var(--color-fg-muted));
}

/*
 * The connector, drawn inside the step's own box rather than in the grid gap:
 * a rule positioned outside would be clipped by the `overflow: hidden` that
 * the ellipsis needs. The first step has neither line nor indent.
 */
.ui-stepper :slotted([data-step])::before {
  content: "";
  position: absolute;
  left: 0;
  top: 50%;
  width: 1rem;
  height: 2px;
  background-color: rgb(var(--color-line));
}

.ui-stepper :slotted([data-step]:first-child) {
  padding-left: 0;
}

.ui-stepper :slotted([data-step]:first-child)::before {
  content: none;
}

.ui-stepper :slotted([data-step="done"]),
.ui-stepper :slotted([data-step="active"]) {
  color: rgb(var(--color-fg));
}

.ui-stepper :slotted([data-step="active"]) {
  font-weight: 600;
}

/* A reached step's incoming connector is filled in; an unreached one is not. */
.ui-stepper :slotted([data-step="done"])::before,
.ui-stepper :slotted([data-step="active"])::before {
  background-color: rgb(var(--color-primary));
}

.ui-stepper[data-compact="true"] :slotted([data-step]) {
  padding-left: 0.875rem;
}

.ui-stepper[data-compact="true"] :slotted([data-step])::before {
  width: 0.625rem;
}
</style>
