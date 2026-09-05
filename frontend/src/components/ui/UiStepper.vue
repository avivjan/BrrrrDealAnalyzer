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
 * what lets a long label truncate instead of stretching its column. That
 * fixed single row is a `md:` and up affordance only: below `md` the track
 * wraps onto as many rows as the width needs, and a label clamps to two
 * lines instead of being ellipsised to a handful of characters.
 *
 * Long labels are ellipsised at `md:` and up; below that they wrap and
 * clamp. Either way the view supplies the `title` attribute that reveals
 * the full text, since only the view has the string.
 */
import { computed, useAttrs } from "vue";

import { cn } from "../../design/cn";

const props = withDefaults(defineProps<{ count: number; compact?: boolean }>(), {
  compact: false,
});

defineOptions({ inheritAttrs: false });

const BASE =
  "ui-stepper grid list-none grid-cols-[repeat(auto-fit,minmax(6rem,1fr))] md:grid-cols-[repeat(var(--steps),minmax(0,1fr))] items-center gap-x-2 gap-y-2";

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
 * Below `md`, the step wraps and clamps to two lines instead of truncating to
 * one: `overflow-wrap: anywhere` lets a long word break, and the `-webkit-box`
 * line-clamp is the only cross-browser way to cap a wrapped block at N lines
 * with a trailing ellipsis. There is no connector at this width — a dash
 * drawn against one row makes no sense once steps wrap onto several.
 *
 * At `md:` and up the track is back to one row (see `BASE`), so the step
 * reverts to today's block + `nowrap` + `text-overflow: ellipsis` — that
 * combination only truncates inline content in a block container, which is
 * the whole reason the columns are `minmax(0, 1fr)` — and the connector
 * returns.
 */
.ui-stepper :slotted([data-step]) {
  position: relative;
  min-width: 0;
  padding-left: 0;
  overflow: hidden;
  overflow-wrap: anywhere;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  color: rgb(var(--color-fg-muted));
}

.ui-stepper :slotted([data-step])::before {
  content: none;
}

@media (min-width: 768px) {
  .ui-stepper :slotted([data-step]) {
    display: block;
    padding-left: 1.25rem;
    white-space: nowrap;
    text-overflow: ellipsis;
  }

  /*
   * The connector, drawn inside the step's own box rather than in the grid
   * gap: a rule positioned outside would be clipped by the `overflow: hidden`
   * that the ellipsis needs.
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

  .ui-stepper[data-compact="true"] :slotted([data-step]) {
    padding-left: 0.875rem;
  }

  .ui-stepper[data-compact="true"] :slotted([data-step])::before {
    width: 0.625rem;
  }
}

/* The first step has neither line nor indent, at any width. */
.ui-stepper :slotted([data-step]:first-child) {
  padding-left: 0;
}

.ui-stepper :slotted([data-step]:first-child)::before {
  content: none;
}

@media (min-width: 768px) {
  /*
   * A compact first step still gets the compact indent (0.875rem, same as
   * every other compact item) at `md:` and up — it just has no connector to
   * indent *for*, unlike its siblings. That has to be true regardless of
   * where this rule sits in the file: `:first-child` here makes this
   * selector strictly more specific than both the plain `:first-child` rule
   * above and the `[data-compact="true"] :slotted([data-step])` rule in the
   * first media block, so the invariant holds by specificity, not by
   * accident of source order (round 1 fix: moving the compact rule into a
   * media block ahead of the plain `:first-child` rule flipped a same-
   * specificity tie and zeroed this out on desktop).
   */
  .ui-stepper[data-compact="true"] :slotted([data-step]:first-child) {
    padding-left: 0.875rem;
  }
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
</style>
