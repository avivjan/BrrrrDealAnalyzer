<script setup lang="ts">
/**
 * A static thumbnail of one look: a sidebar strip, two KPI tiles, a primary
 * button and a sparkline, all drawn with token utilities. The root carries
 * `data-look` and `data-mode`, so the look sheets apply *to this element*
 * regardless of the look the page is showing — every card in the picker shows
 * its own look, in the mode the page is in.
 */
import { cn } from "../../design/cn";
import type { LookId } from "../../design/looks";

withDefaults(defineProps<{ lookId: LookId; mode?: "light" | "dark" }>(), { mode: "dark" });
</script>

<template>
  <span
    :data-look="lookId"
    :data-mode="mode"
    aria-hidden="true"
    :class="
      cn(
        'grid aspect-[16/10] w-full grid-cols-[28%_1fr] gap-1.5 overflow-hidden rounded-card border-ui border-line bg-page p-1.5 text-fg',
      )
    "
  >
    <span class="flex flex-col gap-1 rounded-ctl bg-surface p-1">
      <span class="h-1.5 w-1/2 rounded-full bg-primary shadow-glow-primary" />
      <span class="mt-1 h-1 w-full rounded-full bg-primary/30" />
      <span class="h-1 w-3/4 rounded-full bg-fg/10" />
      <span class="h-1 w-3/4 rounded-full bg-fg/10" />
    </span>
    <span class="flex min-w-0 flex-col gap-1.5">
      <span class="grid grid-cols-2 gap-1.5">
        <span class="flex flex-col gap-1 rounded-ctl border-ui border-line bg-surface p-1.5 shadow-1">
          <span class="h-1 w-1/2 rounded-full bg-fg/20" />
          <span class="font-display text-[9px] font-bold leading-none tracking-display">$4.2M</span>
          <span class="h-0.5 w-1/3 rounded-full bg-positive" />
        </span>
        <span class="flex flex-col gap-1 rounded-ctl border-ui border-line bg-surface p-1.5 shadow-1">
          <span class="h-1 w-1/2 rounded-full bg-fg/20" />
          <span class="font-display text-[9px] font-bold leading-none tracking-display">1.32</span>
          <span class="h-0.5 w-1/3 rounded-full bg-negative" />
        </span>
      </span>
      <span class="flex flex-1 items-end gap-1 rounded-ctl border-ui border-line bg-surface px-1.5 pb-1.5 pt-1 shadow-1">
        <svg viewBox="0 0 100 24" preserveAspectRatio="none" class="h-full w-full text-accent">
          <path d="M0,20 L15,17 L30,18 L45,11 L60,13 L75,6 L90,8 L100,3 L100,24 L0,24 Z" fill="currentColor" opacity="0.15" />
          <path d="M0,20 L15,17 L30,18 L45,11 L60,13 L75,6 L90,8 L100,3" fill="none" stroke="currentColor" stroke-width="2" vector-effect="non-scaling-stroke" />
        </svg>
      </span>
      <span class="inline-flex h-4 w-[55%] items-center justify-center self-end rounded-ctl bg-primary text-[7px] font-semibold text-primary-fg shadow-glow-primary">
        Analyze
      </span>
    </span>
  </span>
</template>
