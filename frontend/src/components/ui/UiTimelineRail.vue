<script setup lang="ts">
/**
 * A step rail — the pipeline stages as a line of dots, each done, active or
 * still to come. Presentational: the caller says which step is which; the
 * rail draws it and marks the active step with `aria-current="step"`.
 *
 * Meaning is carried three ways at once — position, the filled/hollow/ringed
 * dot, and the state attribute the caller's copy or a screen reader can use —
 * so colour never stands alone. Labels wrap under their dot horizontally and
 * sit beside it vertically.
 */
import { computed, useAttrs } from "vue";

import { cn } from "../../design/cn";

export interface TimelineRailItem {
  id: string | number;
  label: string;
  state: "done" | "active" | "todo";
}

const props = withDefaults(
  defineProps<{
    items: TimelineRailItem[];
    orientation?: "horizontal" | "vertical";
    /** Hide the labels visually (they stay in the DOM for assistive tech). */
    compact?: boolean;
  }>(),
  { orientation: "horizontal", compact: false },
);

defineOptions({ inheritAttrs: false });

const DOTS: Record<TimelineRailItem["state"], string> = {
  done: "bg-primary border-primary",
  active: "bg-surface border-primary ring-4 ring-primary/20 shadow-glow-primary",
  todo: "bg-surface border-line",
};

const attrs = useAttrs();

function passthrough() {
  const rest: Record<string, unknown> = { ...attrs };
  delete rest.class;
  return rest;
}

const horizontal = computed(() => props.orientation === "horizontal");

const rootClass = computed(() =>
  cn(
    "flex list-none p-0 m-0",
    horizontal.value ? "flex-row items-start" : "flex-col items-stretch",
    attrs.class as string,
  ),
);
</script>

<template>
  <ol data-ui="timeline-rail" role="list" :data-orientation="orientation" :class="rootClass" v-bind="passthrough()">
    <li
      v-for="(item, index) in items"
      :key="item.id"
      :data-state="item.state"
      :aria-current="item.state === 'active' ? 'step' : undefined"
      :class="
        cn(
          'relative flex min-w-0 flex-1 gap-2',
          horizontal ? 'flex-col items-center text-center' : 'flex-row items-center py-2',
        )
      "
    >
      <!-- The connector to the next dot; done→done is solid primary, anything else the line colour. -->
      <span
        v-if="index < items.length - 1"
        data-part="connector"
        aria-hidden="true"
        :class="
          cn(
            'absolute',
            horizontal ? 'left-1/2 top-[7px] h-0.5 w-full' : 'left-[7px] top-1/2 h-full w-0.5',
            item.state === 'done' ? 'bg-primary' : 'bg-line',
          )
        "
      />
      <span
        data-part="dot"
        aria-hidden="true"
        :class="cn('relative z-[1] h-4 w-4 shrink-0 rounded-full border-2', DOTS[item.state])"
      />
      <span
        data-part="label"
        :class="
          cn(
            'text-xs leading-tight',
            item.state === 'active' ? 'font-semibold text-fg' : 'text-fg-muted',
            compact && 'sr-only',
          )
        "
      >
        {{ item.label }}
      </span>
    </li>
  </ol>
</template>
