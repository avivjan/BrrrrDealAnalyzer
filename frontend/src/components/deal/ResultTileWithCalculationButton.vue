<script setup lang="ts">
/**
 * A result tile of the deal modal that can be pressed to show how its number
 * was calculated.
 *
 * The tile itself stays the plain `UiStatTile` readout the modal always had:
 * the caller's value element goes through the default slot untouched (its
 * `data-testid`, `v-flash` and colour classes included). What this adds is a
 * transparent `<button>` laid over the tile — a sibling, not a wrapper, since
 * a `<div>` may not live inside a `<button>` — with the accessible name
 * "Show how <metric> is calculated", and a small calculator glyph in the
 * caption as the visible hint. Pressing it emits which metric was pressed; the
 * view owns the popup.
 */
const props = defineProps<{
  /** The caption on the tile, e.g. "Cash Flow". */
  metricLabel: string;
  /** The result key the breakdown is filed under, e.g. "cash_flow". */
  metricKey: string;
}>();

const emit = defineEmits<{
  showCalculation: [pressed: { metricKey: string; metricLabel: string }];
}>();

function onShowCalculationPressed() {
  emit("showCalculation", { metricKey: props.metricKey, metricLabel: props.metricLabel });
}
</script>

<template>
  <div data-ui="result-tile-with-calculation-button" class="group/result-tile relative">
    <UiStatTile tone="neutral" class="bg-surface">
      <template #label>
        <span class="inline-flex items-center gap-1">
          <span>{{ metricLabel }}</span>
          <i
            class="pi pi-calculator text-[0.75em] text-fg-muted opacity-60 transition-opacity group-hover/result-tile:opacity-100 group-focus-within/result-tile:opacity-100 touch:opacity-100"
            aria-hidden="true"
          ></i>
        </span>
      </template>
      <slot />
    </UiStatTile>
    <button
      type="button"
      :data-testid="`result-tile.${metricKey}.show-calculation`"
      :aria-label="`Show how ${metricLabel} is calculated`"
      :title="`Show how ${metricLabel} is calculated`"
      class="absolute inset-0 z-[1] cursor-pointer rounded-card outline-none transition-colors hover:bg-primary/5 focus-visible:ring-2 focus-visible:ring-primary touch:bg-transparent"
      @click="onShowCalculationPressed"
    ></button>
  </div>
</template>
