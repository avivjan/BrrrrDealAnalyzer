<script setup lang="ts">
/**
 * A whole-day count with a calendar way in — "Days until Refi", "Days until Tenant Occupied".
 *
 * The field's value is always a day count (what the backend stores and accrues per diem
 * against); the calendar is an easier way to arrive at it. Two modes:
 *
 * - **Anchored** (`anchorDate` given, the deal's Buy closing date): the day count and the
 *   date it lands on sit side by side, linked both ways. Type days → the date follows;
 *   pick a date → the days follow (`date − anchor`). Whichever was edited last governs.
 * - **Unanchored** (no Buy closing date yet): the original picker — two dates in, a day
 *   count out, dates not kept.
 *
 * Native `<input type="date">` rather than PrimeVue's `DatePicker`: PrimeVue runs
 * `unstyled: true` with no preset, so the native control is the styled one.
 */
import { computed, ref, watch } from "vue";
import { useId } from "vue";
import NumberInput from "./NumberInput.vue";
import InputInfo from "./InputInfo.vue";
import { addDays, daysBetween } from "../../utils/brrrAutoCalc";

const props = withDefaults(
  defineProps<{
    modelValue: number | null;
    label: string;
    /** Label of the linked date when hasAnchorDate ("Refi closing"). */
    dateLabel?: string;
    /** ISO date the count starts from. Enables the linked-date mode. */
    anchorDate?: string | null;
    /** Smallest day count accepted (1 for the refi, 0 for a tenant on closing day). */
    min?: number;
    required?: boolean;
    info?: string;
    note?: string;
    /** Why the day count is wrong; handed to the number box. */
    errorMessage?: string;
  }>(),
  { dateLabel: "Date", anchorDate: null, min: 1, required: false, info: undefined, note: undefined, errorMessage: undefined },
);

const emit = defineEmits(["update:modelValue"]);

const hasAnchorDate = computed(() => !!props.anchorDate);

/** The date the day count lands on, when hasAnchorDate. */
const linkedDateIso = computed(() =>
  props.anchorDate && props.modelValue != null ? addDays(props.anchorDate, props.modelValue) : null,
);

/**
 * Why the last picked date was refused, shown under the date box until a date is
 * accepted or the count changes from elsewhere. Refusing silently left the picker
 * snapping back to the old date with no word on why.
 */
const linkedDatePickProblem = ref("");
const linkedDateEarliestAllowed = computed(() => (props.anchorDate ? addDays(props.anchorDate, props.min) : null));

const onLinkedDateChange = (event: Event) => {
  const pickedDateIso = (event.target as HTMLInputElement).value;
  if (!props.anchorDate || !pickedDateIso) return;
  const daysFromAnchor = daysBetween(props.anchorDate, pickedDateIso);
  if (daysFromAnchor == null || daysFromAnchor < props.min) {
    linkedDatePickProblem.value =
      props.min > 0
        ? `Must be after the buy closing date (${props.anchorDate}); the earliest is ${linkedDateEarliestAllowed.value}.`
        : `Must be on or after the buy closing date (${props.anchorDate}).`;
    return;
  }
  linkedDatePickProblem.value = "";
  emit("update:modelValue", daysFromAnchor);
};
watch(() => [props.modelValue, props.anchorDate], () => { linkedDatePickProblem.value = ""; });

// ---- Unanchored picker (the original behaviour) ------------------------------------
const picking = ref(false);
const purchaseDate = ref("");
const refiDate = ref("");

const pickedDays = computed<number | null>(() => {
  if (!purchaseDate.value || !refiDate.value) return null;
  const daysBetweenPickedDates = daysBetween(purchaseDate.value, refiDate.value);
  return daysBetweenPickedDates != null && daysBetweenPickedDates > 0 ? daysBetweenPickedDates : null;
});

const pickerProblem = computed(() => {
  if (!purchaseDate.value || !refiDate.value) return "";
  return pickedDays.value == null ? "The second date must be after the first." : "";
});

const openPicker = () => {
  purchaseDate.value = "";
  refiDate.value = "";
  picking.value = true;
};

const applyPickedDates = () => {
  if (pickedDays.value == null) return;
  emit("update:modelValue", pickedDays.value);
  picking.value = false;
};

const daysInputId = useId();
const linkedDateId = useId();
const purchaseDateId = useId();
const refiDateId = useId();
const linkedDateProblemId = useId();
</script>

<template>
  <div v-if="hasAnchorDate" data-mode="anchored" class="grid grid-cols-2 gap-3">
    <!-- Anchored: days and the date they land on, side by side and linked both ways. -->
    <div class="flex flex-col gap-1.5">
      <div data-part="label-row" class="flex h-5 items-center justify-between gap-2">
        <span class="inline-flex min-w-0 items-center gap-1">
          <label :for="daysInputId" data-part="label" class="truncate text-sm font-medium leading-5 text-fg"
          >{{ label }}<span v-if="required" data-part="required" aria-hidden="true" class="text-negative">*</span><span v-if="required" class="sr-only">required</span></label>
          <InputInfo v-if="info" :content="info" :field-label="label" />
        </span>
      </div>
      <NumberInput
        data-part="input"
        :data-input-id="daysInputId"
        :model-value="modelValue"
        suffix=" days"
        :error-message="errorMessage"
        @update:model-value="(v: number | null) => emit('update:modelValue', v)"
      />
    </div>
    <div class="flex flex-col gap-1.5">
      <div data-part="label-row" class="flex h-5 items-center justify-between gap-2">
        <label :for="linkedDateId" data-part="label" class="truncate text-sm font-medium leading-5 text-fg">{{ dateLabel }}</label>
        <span v-if="note" data-part="note" class="numeric shrink-0 truncate text-xs font-medium leading-5 text-fg-muted">{{ note }}</span>
      </div>
      <input
        data-part="date-linked"
        :id="linkedDateId"
        type="date"
        :value="linkedDateIso ?? ''"
        :min="linkedDateEarliestAllowed ?? undefined"
        class="ui-input"
        :class="linkedDatePickProblem ? 'ui-input-invalid' : ''"
        :aria-invalid="linkedDatePickProblem ? 'true' : undefined"
        :aria-describedby="linkedDatePickProblem ? linkedDateProblemId : undefined"
        v-shake="linkedDatePickProblem"
        @change="onLinkedDateChange"
      />
      <p v-if="linkedDatePickProblem" :id="linkedDateProblemId" role="alert" data-part="date-linked-problem" class="text-xs text-negative">{{ linkedDatePickProblem }}</p>
    </div>
  </div>

  <div v-else data-mode="picker" class="flex flex-col gap-1.5">
    <!-- Unanchored: the day count, with a calendar to derive it from two dates. -->
    <div data-part="label-row" class="flex h-5 items-center justify-between gap-2">
      <span class="inline-flex min-w-0 items-center gap-1">
        <label :for="daysInputId" data-part="label" class="truncate text-sm font-medium leading-5 text-fg"
        >{{ label }}<span v-if="required" data-part="required" aria-hidden="true" class="text-negative">*</span><span v-if="required" class="sr-only">required</span></label>
        <InputInfo v-if="info" :content="info" :field-label="label" />
      </span>
      <button
        type="button"
        data-part="toggle"
        class="inline-flex h-5 items-center gap-1 text-xs font-medium text-primary hover:text-primary-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded-ctl touch:min-h-11 touch:-my-3"
        @click="picking ? (picking = false) : openPicker()"
      >
        <i class="pi pi-calendar text-[11px]" aria-hidden="true"></i>
        {{ picking ? "Enter days instead" : "Pick dates" }}
      </button>
    </div>

    <NumberInput
      v-if="!picking"
      data-part="input"
      :data-input-id="daysInputId"
      :model-value="modelValue"
      suffix=" days"
      :error-message="errorMessage"
      @update:model-value="(v: number | null) => emit('update:modelValue', v)"
    />

    <div v-else class="flex flex-col gap-3 rounded-card border border-line bg-surface-muted p-3">
      <div class="grid grid-cols-2 gap-3">
        <div class="flex flex-col gap-1">
          <label :for="purchaseDateId" class="text-xs font-medium text-fg-muted">From</label>
          <input data-part="date-purchase" :id="purchaseDateId" v-model="purchaseDate" type="date" class="ui-input" />
        </div>
        <div class="flex flex-col gap-1">
          <label :for="refiDateId" class="text-xs font-medium text-fg-muted">{{ dateLabel }}</label>
          <input data-part="date-refi" :id="refiDateId" v-model="refiDate" type="date" :min="purchaseDate || undefined" class="ui-input" />
        </div>
      </div>
      <div class="flex items-center justify-between gap-3">
        <span v-if="pickerProblem" class="text-xs text-negative">{{ pickerProblem }}</span>
        <span v-else-if="pickedDays != null" class="numeric text-sm font-semibold text-fg">{{ pickedDays.toLocaleString() }} days</span>
        <span v-else class="text-xs text-fg-muted">Pick both dates to get the day count.</span>
        <UiButton type="button" data-part="done" size="sm" class="touch:min-h-11" :disabled="pickedDays == null" @click="applyPickedDates">
          Done
        </UiButton>
      </div>
    </div>
  </div>
</template>
