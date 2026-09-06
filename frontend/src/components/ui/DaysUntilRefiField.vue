<script setup lang="ts">
/**
 * "Days until Refi" — the hold between purchase closing and refi closing.
 *
 * Two ways in, one value out. The field's value is always a whole day count
 * (what the backend stores and accrues HML interest against, per diem on a
 * 360-day year); the calendar is purely an easier way to arrive at that number,
 * the way a flight search takes two dates and shows you a trip length.
 *
 * The dates themselves are deliberately *not* stored — only the day count they
 * produce. Picking dates again later is one click, and it keeps the deal record
 * honest about what actually feeds the calculation.
 *
 * Native `<input type="date">` rather than PrimeVue's `DatePicker`: PrimeVue is
 * configured `unstyled: true` with no preset (`main.ts`), so a `DatePicker`
 * would arrive with no styling at all and need its entire panel/header/grid
 * hand-written in `pt`. The native control brings the OS calendar popover and
 * takes our Tailwind classes directly.
 */
import { computed, ref } from "vue";
import { useId } from "vue";
import NumberInput from "./NumberInput.vue";

defineProps<{
  modelValue: number | null;
  label: string;
  required?: boolean;
}>();

const emit = defineEmits(["update:modelValue"]);

const picking = ref(false);
const purchaseDate = ref("");
const refiDate = ref("");

const MS_PER_DAY = 86_400_000;

/** Whole days between the two dates, or `null` until both are valid. */
const pickedDays = computed<number | null>(() => {
  if (!purchaseDate.value || !refiDate.value) return null;
  const from = Date.parse(`${purchaseDate.value}T00:00:00`);
  const to = Date.parse(`${refiDate.value}T00:00:00`);
  if (Number.isNaN(from) || Number.isNaN(to)) return null;
  const days = Math.round((to - from) / MS_PER_DAY);
  return days > 0 ? days : null;
});

/** Why `Done` is unavailable, if it is. Doubles as the inline error text. */
const pickerProblem = computed(() => {
  if (!purchaseDate.value || !refiDate.value) return "";
  return pickedDays.value == null ? "Refi date must be after the purchase date." : "";
});

const openPicker = () => {
  // Start blank each time — the dates aren't persisted, so any previous pair
  // would just be a stale guess at what produced the current day count.
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
const purchaseDateId = useId();
const refiDateId = useId();
</script>

<template>
  <div class="flex flex-col gap-1.5">
    <!--
      The mode toggle is a plain text control, not a `UiButton`: it sits inside
      the 20px label row and must not grow it, or this field's box would land
      below its neighbours'. On touch the 44px target comes from a negative
      vertical margin, so the row keeps its height there too.
    -->
    <div data-part="label-row" class="flex h-5 items-center justify-between gap-2">
      <label
        :for="daysInputId"
        data-part="label"
        class="text-sm font-medium leading-5 text-fg"
      >{{ label }}<span v-if="required" data-part="required" aria-hidden="true" class="text-negative">*</span><span v-if="required" class="sr-only">required</span></label>
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

    <!-- Default: type the number of days straight in. -->
    <NumberInput
      v-if="!picking"
      data-part="input"
      :data-input-id="daysInputId"
      :model-value="modelValue"
      suffix=" days"
      :min="1"
      @update:model-value="(v: number | null) => emit('update:modelValue', v)"
    />

    <!-- Calendar: two dates in, a day count out. -->
    <div
      v-else
      class="flex flex-col gap-3 rounded-card border border-line bg-surface-muted p-3"
    >
      <div class="grid grid-cols-2 gap-3">
        <div class="flex flex-col gap-1">
          <label :for="purchaseDateId" class="text-xs font-medium text-fg-muted">Purchase closing</label>
          <input data-part="date-purchase" :id="purchaseDateId" v-model="purchaseDate" type="date" class="ui-input" />
        </div>
        <div class="flex flex-col gap-1">
          <label :for="refiDateId" class="text-xs font-medium text-fg-muted">Refi closing</label>
          <input
            data-part="date-refi"
            :id="refiDateId"
            v-model="refiDate"
            type="date"
            :min="purchaseDate || undefined"
            class="ui-input"
          />
        </div>
      </div>

      <div class="flex items-center justify-between gap-3">
        <span
          v-if="pickerProblem"
          class="text-xs text-negative"
        >{{ pickerProblem }}</span>
        <span
          v-else-if="pickedDays != null"
          class="numeric text-sm font-semibold text-fg"
        >{{ pickedDays.toLocaleString() }} days</span>
        <span v-else class="text-xs text-fg-muted">
          Pick both dates to get the day count.
        </span>

        <UiButton
          type="button"
          data-part="done"
          size="sm"
          class="touch:min-h-11"
          :disabled="pickedDays == null"
          @click="applyPickedDates"
        >
          Done
        </UiButton>
      </div>
    </div>

  </div>
</template>
