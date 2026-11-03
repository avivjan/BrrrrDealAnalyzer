<script setup lang="ts">
/**
 * A monthly reserve of a regular year after the refi (vacancy, maintenance, CapEx, management)
 * typed either as a percentage of the rent or as dollars per month.
 *
 * Two fields behind one box: the percentage, and a nullable monthly-dollar override. `null`
 * dollars = the percentage applies; a number = the dollars win (the backend's `effective`). The
 * small `% | $` pill in the label row switches between them:
 * - to `$`: the dollars are seeded with what the percentage gives today (rent × %), so nothing moves;
 * - to `%`: the dollars go back to `null`, and the percentage is seeded from dollars ÷ rent when
 *   there is a rent to divide by.
 * The muted line under the box always shows the other unit ("≈ $75/mo", "≈ 5% of rent").
 */
import { computed, ref } from "vue";
import { formatMoney } from "../../utils/money";
import NumberInput from "./NumberInput.vue";
import MoneyInput from "./MoneyInput.vue";

type ReserveUnit = "percentOfRent" | "monthlyDollars";

const props = defineProps<{
  label: string;
  percentOfRent: number | null;
  /** `null` = the percentage applies. */
  monthlyDollars: number | null;
  /** The monthly rent in dollars, for the conversions; `null` / 0 while it is not typed. */
  monthlyRentDollars: number | null;
  info?: string;
  percentErrorMessage?: string;
  dollarsErrorMessage?: string;
}>();

const emit = defineEmits<{
  "update:percentOfRent": [value: number | null];
  "update:monthlyDollars": [value: number | null];
}>();

const UNIT_OPTIONS: { unit: ReserveUnit; symbol: string; accessibleLabel: string }[] = [
  { unit: "percentOfRent", symbol: "%", accessibleLabel: "Percent of rent" },
  { unit: "monthlyDollars", symbol: "$", accessibleLabel: "Dollars per month" },
];

const selectedUnit = computed<ReserveUnit>(() => (props.monthlyDollars != null ? "monthlyDollars" : "percentOfRent"));
const rentIsKnown = computed(() => props.monthlyRentDollars != null && props.monthlyRentDollars > 0);
const roundToCents = (value: number) => Math.round(value * 100) / 100;

const monthlyDollarsFromPercent = computed(() =>
  rentIsKnown.value ? roundToCents((props.monthlyRentDollars! * (props.percentOfRent ?? 0)) / 100) : null,
);
const percentFromMonthlyDollars = computed(() =>
  rentIsKnown.value && props.monthlyDollars != null ? roundToCents((props.monthlyDollars / props.monthlyRentDollars!) * 100) : null,
);

const otherUnitReading = computed(() => {
  if (selectedUnit.value === "monthlyDollars") {
    return percentFromMonthlyDollars.value == null ? "per month" : `per month · ≈ ${percentFromMonthlyDollars.value}% of rent`;
  }
  return monthlyDollarsFromPercent.value == null ? "of the monthly rent" : `of rent · ≈ ${formatMoney(monthlyDollarsFromPercent.value)}/mo`;
});

const chooseUnit = (unit: ReserveUnit) => {
  if (unit === selectedUnit.value) return;
  if (unit === "monthlyDollars") {
    emit("update:monthlyDollars", monthlyDollarsFromPercent.value ?? 0);
    return;
  }
  if (percentFromMonthlyDollars.value != null) emit("update:percentOfRent", percentFromMonthlyDollars.value);
  emit("update:monthlyDollars", null);
};

const unitButtons = ref<HTMLButtonElement[]>([]);
/** Radiogroup keyboard pattern: the arrow keys move the choice, and focus follows it. */
const onUnitKeydown = (event: KeyboardEvent) => {
  if (!["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"].includes(event.key)) return;
  event.preventDefault();
  const nextUnit: ReserveUnit = selectedUnit.value === "percentOfRent" ? "monthlyDollars" : "percentOfRent";
  chooseUnit(nextUnit);
  unitButtons.value[UNIT_OPTIONS.findIndex((option) => option.unit === nextUnit)]?.focus();
};
</script>

<template>
  <div data-ui="percent-of-rent-or-monthly-dollars" :data-unit="selectedUnit" class="relative flex flex-col gap-1">
    <NumberInput
      v-if="selectedUnit === 'percentOfRent'"
      data-part="percent-input"
      :model-value="percentOfRent"
      :label="label"
      suffix="%"
      :info="info"
      :error-message="percentErrorMessage"
      @update:model-value="(value: number | null) => emit('update:percentOfRent', value)"
    />
    <MoneyInput
      v-else
      data-part="dollars-input"
      :model-value="monthlyDollars"
      :label="label"
      :min="0"
      :info="info"
      :error-message="dollarsErrorMessage"
      @update:model-value="(value: number | null) => emit('update:monthlyDollars', value)"
    />
    <div
      role="radiogroup"
      :aria-label="`${label}: percent of rent or dollars per month`"
      data-part="unit-toggle"
      class="absolute right-0 top-0 inline-flex h-5 items-center rounded-full bg-surface-3 p-0.5"
      @keydown="onUnitKeydown"
    >
      <button
        v-for="option in UNIT_OPTIONS"
        :key="option.unit"
        ref="unitButtons"
        type="button"
        role="radio"
        :data-unit="option.unit"
        :aria-checked="option.unit === selectedUnit"
        :aria-label="option.accessibleLabel"
        :tabindex="option.unit === selectedUnit ? 0 : -1"
        class="inline-flex h-4 min-w-[1.375rem] items-center justify-center rounded-full px-1.5 text-[11px] font-semibold leading-none transition-[color,background-color,box-shadow] duration-fast ease-standard focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        :class="option.unit === selectedUnit ? 'bg-surface text-fg shadow-1' : 'text-fg-muted hover:text-fg'"
        @click="chooseUnit(option.unit)"
      >{{ option.symbol }}</button>
    </div>
    <p data-part="other-unit" class="numeric truncate text-xs leading-4 text-fg-muted">{{ otherUnitReading }}</p>
  </div>
</template>
