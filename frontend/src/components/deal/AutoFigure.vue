<script setup lang="ts">
/**
 * An auto-calculated dollar figure shown beside the inputs that feed it — "Cash to Close
 * (Buy) $16,386". Renders nothing while `value` is null (an input it needs is missing),
 * which is the rule for every derived figure on the form.
 */
import { computed } from "vue";
import { formatMoney } from "../../utils/money";

const props = withDefaults(
  defineProps<{
    label: string;
    value: number | null | undefined;
    /** Colour the figure by its sign (a negative wire, a positive credit). */
    signed?: boolean;
    /** A short aside under the label ("22 days through Jan 31"). */
    hint?: string;
  }>(),
  { signed: false, hint: undefined },
);

const valueToneClass = computed(() => {
  if (!props.signed || props.value == null || props.value === 0) return "text-fg";
  return props.value > 0 ? "text-positive" : "text-negative";
});
</script>

<template>
  <div
    v-if="value != null"
    data-ui="auto-figure"
    class="flex items-baseline justify-between gap-3 rounded-ctl bg-surface-3/60 px-3 py-2"
  >
    <span class="min-w-0">
      <span data-part="label" class="block text-xs font-medium text-fg-muted">{{ label }}</span>
      <span v-if="hint" data-part="hint" class="block text-[11px] text-fg-muted">{{ hint }}</span>
    </span>
    <span data-part="value" class="numeric shrink-0 text-sm font-semibold" :class="valueToneClass">{{ formatMoney(value) }}</span>
  </div>
</template>
