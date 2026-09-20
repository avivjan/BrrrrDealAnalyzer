<script setup lang="ts">
/**
 * A money field whose value is "the formula unless you say otherwise".
 *
 * `modelValue === null` means the backend applies its formula default (recording fees,
 * title charges, the vacancy reserve, the lowest ARV). While null the box shows the
 * computed default greyed, with an "auto" tag; typing a number overrides it and the tag
 * becomes a ↺ that puts the formula back. The same anatomy as `MoneyInput`, which it wraps.
 */
import { computed } from "vue";
import MoneyInput from "./MoneyInput.vue";

const props = defineProps<{
  /** `null` = use the formula; a number = the override. In thousands when `inThousands`. */
  modelValue: number | null;
  /** What the formula gives right now (same unit as `modelValue`); `null` while its inputs are missing. */
  computedDefault: number | null;
  label: string;
  inThousands?: boolean;
  required?: boolean;
  info?: string;
}>();

const emit = defineEmits(["update:modelValue"]);

const usesFormulaDefault = computed(() => props.modelValue == null);
/** What the box displays: the override, or the formula's current value. */
const displayedValue = computed(() => (usesFormulaDefault.value ? props.computedDefault : props.modelValue));

const onAmountUpdate = (value: number | null) => {
  // Clearing the box returns to the formula, exactly like pressing ↺.
  emit("update:modelValue", value);
};
</script>

<template>
  <div data-ui="auto-default-money" :data-auto="usesFormulaDefault" class="relative">
    <MoneyInput
      :model-value="displayedValue"
      :label="label"
      :in-thousands="inThousands"
      :required="required"
      :info="info"
      :class="usesFormulaDefault ? '[&_input]:text-fg-muted' : ''"
      @update:model-value="onAmountUpdate"
    />
    <span
      v-if="usesFormulaDefault"
      data-part="auto"
      class="pointer-events-none absolute right-2 top-0 inline-flex h-5 items-center rounded-ctl bg-surface-3 px-1.5 text-[10px] font-medium uppercase tracking-wide text-fg-muted"
    >auto</span>
    <button
      v-else
      type="button"
      data-part="reset"
      class="absolute right-2 top-0 inline-flex h-5 items-center gap-1 rounded-ctl text-xs font-medium text-primary hover:text-primary-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring touch:min-h-11 touch:-my-3"
      aria-label="Use the formula default"
      @click="emit('update:modelValue', null)"
    >
      <i class="pi pi-refresh text-[11px]" aria-hidden="true"></i> auto
    </button>
  </div>
</template>
