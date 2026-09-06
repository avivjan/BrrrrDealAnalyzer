<script setup lang="ts">
/**
 * One stage of a pipeline board: a numbered header node on the rail, the
 * stage name, a count chip and an optional legend of the stage's tasks, over a
 * body the view fills (the `VueDraggable`, which stays in the view because its
 * handlers need the view's scope).
 *
 * Presentational only. On `lg+` the board lays these out as scroll-snapped
 * columns joined by the connector each header draws to the next; below `lg`
 * they stack full-width, which is what the phones already rendered. The
 * connector and every state here are CSS — nothing in a column tweens, so
 * SortableJS (which owns the body's DOM) is never fought.
 */
import { computed, ref } from "vue";

import { cn } from "../../design/cn";

const props = withDefaults(
  defineProps<{
    name: string;
    count: number;
    /** 1-based position on the rail. */
    index: number;
    total: number;
    /** The stage's fill class on the ramp (`bg-chart-4` … `bg-positive`). */
    tone: string;
    /** Task labels shown under a disclosure in the header; none hides it. */
    legend?: string[];
    /** The last stage: rendered as "done", no connector after it. */
    terminal?: boolean;
    /** Faded and inert while a drag could not legally land here. */
    inert?: boolean;
  }>(),
  { legend: () => [], terminal: false, inert: false },
);

const legendOpen = ref(false);
const isLast = computed(() => props.index >= props.total);

const rootClass = computed(() =>
  cn(
    "relative flex w-full shrink-0 flex-col rounded-card border-ui border-line bg-surface shadow-1",
    "lg:w-[22rem] lg:snap-start",
    "transition-[opacity] duration-fast ease-standard",
    props.inert && "pointer-events-none opacity-50",
  ),
);
</script>

<template>
  <section :class="rootClass" :data-stage-index="index" :aria-label="name">
    <!-- Header node on the rail. Sticky inside the column so the name stays put while the column scrolls. -->
    <header class="sticky top-0 z-10 rounded-t-card border-b border-line bg-surface/95 px-3 pb-2 pt-3">
      <!-- Connector to the next column (lg+ only): the rail is these segments joined end to end. -->
      <span
        v-if="!isLast"
        aria-hidden="true"
        class="pointer-events-none absolute left-1/2 top-[1.375rem] hidden h-0.5 w-[calc(50%+1rem)] lg:block"
        :class="terminal ? 'bg-positive/40' : 'bg-line'"
      ></span>
      <div class="relative flex items-center gap-2">
        <span
          data-part="node"
          class="grid h-6 w-6 shrink-0 place-items-center rounded-full text-[11px] font-bold text-primary-fg ring-4 ring-surface"
          :class="tone"
        >
          <i v-if="terminal" class="pi pi-check text-[10px]" aria-hidden="true"></i>
          <span v-else class="numeric">{{ index }}</span>
        </span>
        <h3 class="min-w-0 flex-1 truncate font-display text-base font-semibold tracking-display text-fg">
          {{ name }}
        </h3>
        <UiChip size="sm" data-part="count"><span class="numeric">{{ count }}</span></UiChip>
      </div>
      <div v-if="legend.length" class="mt-1.5">
        <button
          type="button"
          data-part="legend-toggle"
          class="inline-flex h-5 items-center gap-1 rounded-ctl text-[11px] text-fg-muted hover:text-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring touch:min-h-11 touch:-my-3"
          :aria-expanded="legendOpen"
          @click="legendOpen = !legendOpen"
        >
          <i class="pi text-[10px]" :class="legendOpen ? 'pi-chevron-down' : 'pi-chevron-right'" aria-hidden="true"></i>
          {{ legend.length }} task{{ legend.length === 1 ? "" : "s" }} to leave this stage
        </button>
        <ul v-if="legendOpen" data-part="legend" class="mt-1 space-y-0.5 pl-4 text-[11px] text-fg-muted">
          <li v-for="item in legend" :key="item" class="list-disc">{{ item }}</li>
        </ul>
      </div>
    </header>

    <div class="flex-1 p-3">
      <slot />
      <slot name="empty" />
    </div>
  </section>
</template>
