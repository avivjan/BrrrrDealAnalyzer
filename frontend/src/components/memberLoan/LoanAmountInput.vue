<script setup lang="ts">
/**
 * A strict dollar amount: digits with up to two decimals, read exactly as typed.
 * No shorthand ("50" is $50.00), unlike the deal form's MoneyInput, and no
 * floating point: the model is the API's text ("1000.00") or null.
 */
import { computed, ref, watch } from "vue";

import { formatLoanMoney, parseLoanAmountTyped } from "../../utils/memberLoanText";

const props = defineProps<{ modelValue: string | null; id: string; label: string }>();
const emit = defineEmits<{ "update:modelValue": [value: string | null] }>();

const typedText = ref(props.modelValue ?? "");
const touched = ref(false);
const parsedAmount = computed(() => parseLoanAmountTyped(typedText.value));
const invalid = computed(() => touched.value && typedText.value.trim() !== "" && parsedAmount.value === null);

watch(
  () => props.modelValue,
  (value) => {
    if (value !== parsedAmount.value) typedText.value = value ?? "";
  },
);

function onInput(event: Event) {
  typedText.value = (event.target as HTMLInputElement).value;
  emit("update:modelValue", parsedAmount.value);
}
</script>

<template>
  <div class="flex flex-col gap-1">
    <label :for="id" class="text-sm font-medium text-fg">{{ label }}</label>
    <div class="relative">
      <span class="pointer-events-none absolute inset-y-0 left-3 flex items-center text-fg-muted" aria-hidden="true">$</span>
      <input
        :id="id"
        :value="typedText"
        type="text"
        inputmode="decimal"
        autocomplete="off"
        :aria-invalid="invalid || undefined"
        :aria-describedby="`${id}-helper`"
        class="w-full rounded-ctl border border-line bg-page py-2 pl-7 pr-3 text-fg tabular-nums focus:outline-none focus:ring-2 focus:ring-primary/50"
        :class="invalid && 'border-negative'"
        data-testid="member-loan.amount-input"
        @input="onInput"
        @blur="touched = true"
      />
    </div>
    <p :id="`${id}-helper`" class="text-xs" :class="invalid ? 'text-negative' : 'text-fg-muted'" data-testid="member-loan.amount-helper">
      <template v-if="invalid">Type an amount like 1000 or 1000.50 (at most two decimals).</template>
      <template v-else-if="parsedAmount">Exactly {{ formatLoanMoney(parsedAmount) }}</template>
      <template v-else>Dollars and cents, exactly as you type them.</template>
    </p>
  </div>
</template>
