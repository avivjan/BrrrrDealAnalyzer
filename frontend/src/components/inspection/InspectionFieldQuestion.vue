<script setup lang="ts">
/**
 * One field question on an item card, rendered from its config type:
 *   choice            big chips, one tap
 *   year_or_unknown   −/+ year stepper (tap the year to type it) and an "Unknown" chip
 *   text_or_unknown   a text box and an "Unknown" chip
 *   date_or_unknown   a date picker and an "Unknown" chip
 *   counter           the huge window-replacement stepper
 *   text              a text box
 * Emits the new value, or `null` to clear the answer.
 */
import { computed, ref, watch } from "vue";

import {
  UNKNOWN_FIELD_VALUE,
  approximateAgeLabel,
  type InspectionFieldConfig,
  type InspectionFieldValue,
} from "../../inspection/inspectionChecklistLogic";
import InspectionWindowReplacementCounter from "./InspectionWindowReplacementCounter.vue";

const props = defineProps<{ field: InspectionFieldConfig; modelValue: InspectionFieldValue | undefined }>();
const emit = defineEmits<{ "update:modelValue": [value: InspectionFieldValue | null] }>();

const EARLIEST_ALLOWED_YEAR = 1900;
const currentYear = new Date().getFullYear();
const YEAR_STEPPER_STARTING_YEAR = currentYear - 10;

const isUnknown = computed(() => props.modelValue === UNKNOWN_FIELD_VALUE);
const yearValue = computed(() => (typeof props.modelValue === "number" ? props.modelValue : undefined));
const textDraft = ref(typeof props.modelValue === "string" && !isUnknown.value ? props.modelValue : "");
watch(
  () => props.modelValue,
  (value) => {
    if (typeof value === "string" && value !== UNKNOWN_FIELD_VALUE) textDraft.value = value;
    if (value === undefined) textDraft.value = "";
  },
);

const todayIso = new Date().toISOString().slice(0, 10);

function stepYear(by: number) {
  const startingYear = yearValue.value ?? YEAR_STEPPER_STARTING_YEAR - by;
  emit("update:modelValue", Math.min(currentYear + 1, Math.max(EARLIEST_ALLOWED_YEAR, startingYear + by)));
}

function onYearTyped(event: Event) {
  const typedYear = Number((event.target as HTMLInputElement).value);
  if (Number.isInteger(typedYear) && typedYear >= EARLIEST_ALLOWED_YEAR && typedYear <= currentYear + 1) emit("update:modelValue", typedYear);
}

function commitText() {
  const trimmed = textDraft.value.trim();
  if (trimmed === "" && props.modelValue === undefined) return;
  emit("update:modelValue", trimmed === "" ? null : trimmed);
}

function onDatePicked(event: Event) {
  const pickedDate = (event.target as HTMLInputElement).value;
  emit("update:modelValue", pickedDate || null);
}

const choiceClass = (selected: boolean) =>
  selected ? "border-primary bg-primary text-primary-fg shadow-2" : "border-line bg-surface text-fg hover:border-fg-muted";
const testIdBase = computed(() => `inspection.field.${props.field.key}`);
</script>

<template>
  <fieldset class="min-w-0">
    <legend class="mb-3 text-base font-semibold text-fg">{{ field.label }}</legend>

    <div v-if="field.type === 'choice'" class="flex flex-wrap gap-2">
      <button
        v-for="option in field.options"
        :key="option.value"
        type="button"
        :aria-pressed="modelValue === option.value"
        :data-testid="`${testIdBase}.${option.value}`"
        class="inspection-press min-h-14 rounded-ctl border-2 px-4 text-base font-medium transition-[background-color,border-color,color] duration-fast ease-standard focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        :class="choiceClass(modelValue === option.value)"
        @click="emit('update:modelValue', option.value)"
      >
        {{ option.label }}
      </button>
    </div>

    <div v-else-if="field.type === 'year_or_unknown'" class="flex flex-wrap items-center gap-3">
      <div class="flex items-center gap-2 rounded-card border border-line bg-surface-2/60 p-2" :class="isUnknown ? 'opacity-50' : ''">
        <button type="button" :data-testid="`${testIdBase}.decrease`" aria-label="One year earlier" class="inspection-press grid size-14 place-items-center rounded-full border border-line bg-surface text-xl text-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" @click="stepYear(-1)">
          <i class="pi pi-minus" aria-hidden="true"></i>
        </button>
        <input
          :data-testid="`${testIdBase}.year`"
          :value="yearValue ?? ''"
          :placeholder="String(YEAR_STEPPER_STARTING_YEAR)"
          inputmode="numeric"
          maxlength="4"
          :aria-label="field.label"
          class="numeric w-24 rounded-ctl border border-transparent bg-transparent text-center font-display text-3xl text-fg placeholder:text-fg-muted/50 focus:border-line focus:outline-none"
          @change="onYearTyped"
        />
        <button type="button" :data-testid="`${testIdBase}.increase`" aria-label="One year later" class="inspection-press grid size-14 place-items-center rounded-full border border-line bg-surface text-xl text-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" @click="stepYear(1)">
          <i class="pi pi-plus" aria-hidden="true"></i>
        </button>
      </div>
      <button type="button" :aria-pressed="isUnknown" :data-testid="`${testIdBase}.unknown`" class="inspection-press min-h-14 rounded-ctl border-2 px-4 text-base font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" :class="choiceClass(isUnknown)" @click="emit('update:modelValue', UNKNOWN_FIELD_VALUE)">
        Unknown
      </button>
      <p v-if="yearValue" class="w-full text-sm text-fg-muted">{{ approximateAgeLabel(yearValue) }}</p>
    </div>

    <div v-else-if="field.type === 'date_or_unknown'" class="flex flex-wrap items-center gap-3">
      <input
        type="date"
        :data-testid="`${testIdBase}.date`"
        :max="todayIso"
        :value="!isUnknown && typeof modelValue === 'string' ? modelValue : ''"
        :aria-label="field.label"
        class="ui-input min-h-14 max-w-[14rem] text-base"
        @change="onDatePicked"
      />
      <button type="button" :aria-pressed="isUnknown" :data-testid="`${testIdBase}.unknown`" class="inspection-press min-h-14 rounded-ctl border-2 px-4 text-base font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" :class="choiceClass(isUnknown)" @click="emit('update:modelValue', UNKNOWN_FIELD_VALUE)">
        Unknown
      </button>
    </div>

    <InspectionWindowReplacementCounter
      v-else-if="field.type === 'counter'"
      :field="field"
      :model-value="typeof modelValue === 'number' ? modelValue : undefined"
      @update:model-value="emit('update:modelValue', $event)"
    />

    <div v-else class="flex flex-wrap items-center gap-3">
      <input
        v-model="textDraft"
        :data-testid="`${testIdBase}.text`"
        :maxlength="field.type === 'text_or_unknown' ? 120 : 500"
        :aria-label="field.label"
        :placeholder="field.type === 'text_or_unknown' ? 'Type it, or tap Unknown' : ''"
        class="ui-input min-h-14 min-w-0 flex-1 text-base"
        @change="commitText"
        @keydown.enter.prevent="commitText"
      />
      <button v-if="field.type === 'text_or_unknown'" type="button" :aria-pressed="isUnknown" :data-testid="`${testIdBase}.unknown`" class="inspection-press min-h-14 rounded-ctl border-2 px-4 text-base font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" :class="choiceClass(isUnknown)" @click="emit('update:modelValue', UNKNOWN_FIELD_VALUE)">
        Unknown
      </button>
    </div>
  </fieldset>
</template>
