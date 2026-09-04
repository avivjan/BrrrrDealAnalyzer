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

const dateInputClass =
  "w-full bg-white border border-gray-300 rounded-lg px-3 py-2 text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500 transition-all hover:bg-gray-50";
</script>

<template>
  <div class="flex flex-col gap-1.5">
    <div class="flex items-center justify-between">
      <label
        data-part="label"
        class="text-sm font-medium text-gray-700"
        :class="{
          'after:content-[\'*\'] after:ml-0.5 after:text-red-500': required,
        }"
      >
        {{ label }}
      </label>
      <button
        type="button"
        data-part="toggle"
        class="text-xs text-blue-600 hover:text-blue-700 hover:underline focus:outline-none focus:ring-2 focus:ring-blue-300 rounded px-1"
        @click="picking ? (picking = false) : openPicker()"
      >
        <i class="pi pi-calendar text-[11px]"></i>
        {{ picking ? "Enter days instead" : "Pick dates" }}
      </button>
    </div>

    <!-- Default: type the number of days straight in. -->
    <NumberInput
      v-if="!picking"
      data-part="input"
      :model-value="modelValue"
      suffix=" days"
      :min="1"
      @update:model-value="(v: number | null) => emit('update:modelValue', v)"
    />

    <!-- Calendar: two dates in, a day count out. -->
    <div
      v-else
      class="rounded-lg border border-gray-200 bg-gray-50 p-3 flex flex-col gap-3"
    >
      <div class="grid grid-cols-2 gap-3">
        <div class="flex flex-col gap-1">
          <span class="text-xs font-medium text-gray-600">Purchase closing</span>
          <input data-part="date-purchase" v-model="purchaseDate" type="date" :class="dateInputClass" />
        </div>
        <div class="flex flex-col gap-1">
          <span class="text-xs font-medium text-gray-600">Refi closing</span>
          <input
            data-part="date-refi"
            v-model="refiDate"
            type="date"
            :min="purchaseDate || undefined"
            :class="dateInputClass"
          />
        </div>
      </div>

      <div class="flex items-center justify-between gap-3">
        <span
          v-if="pickerProblem"
          class="text-xs text-red-600"
        >{{ pickerProblem }}</span>
        <span
          v-else-if="pickedDays != null"
          class="text-sm font-semibold text-gray-800"
        >{{ pickedDays.toLocaleString() }} days</span>
        <span v-else class="text-xs text-gray-500">
          Pick both dates to get the day count.
        </span>

        <button
          type="button"
          data-part="done"
          :disabled="pickedDays == null"
          class="px-3 py-1.5 text-sm rounded-lg bg-blue-500 text-white shadow-sm transition-colors hover:bg-blue-600 disabled:bg-gray-300 disabled:cursor-not-allowed"
          @click="applyPickedDates"
        >
          Done
        </button>
      </div>
    </div>
  </div>
</template>
