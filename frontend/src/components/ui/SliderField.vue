<script setup lang="ts">
/**
 * A number box paired with a slider (LTV, long-term interest rate).
 *
 * Three deliberate details:
 *
 * - **One emit path**, for the same reason as `NumberInput` — binding `v-model`
 *   *and* `@input` wrote twice per keystroke and made the caret jump.
 * - **The slider's range is not the input's range.** `sliderMin`/`sliderMax`
 *   bound where the thumb can travel, so it can cover the realistic span
 *   (3-12% for a DSCR rate) and stay precise under the mouse. `min`/`max` are
 *   only the thumb's fallback bounds: the typed box is not clamped at all.
 *   PrimeVue used to clamp it on blur through `update:modelValue`, which nobody
 *   listened to, so the box showed `100` while the model kept `150`. A wrong
 *   value is reported by `errorMessage` (from `utils/dealInputValidation`),
 *   never rewritten.
 * - **No fraction mask** (`minFractionDigits: 0`), so `7` doesn't render as
 *   `7.00` and eat your backspaces.
 */
import InputNumber from "primevue/inputnumber";
import Slider from "primevue/slider";
import InputInfo from "./InputInfo.vue";
import { useId } from "vue";
import { computed } from "vue";

const props = defineProps<{
  modelValue: number | null;
  label: string;
  /** Bounds for the slider thumb when `sliderMin`/`sliderMax` are not given. */
  min: number;
  max: number;
  /** Bounds for the slider thumb. Defaults to `min`/`max`. */
  sliderMin?: number;
  sliderMax?: number;
  step?: number;
  suffix?: string;
  required?: boolean;
  /** Tooltip text for the (i) beside the label (what this input affects). */
  info?: string;
  /** A derived reading shown at the right of the label row ("refi loan $240,000"). */
  note?: string;
  /** Why the current value is wrong; outlines the box, shakes it once, and shows the text underneath. */
  errorMessage?: string;
}>();

const emit = defineEmits(["update:modelValue"]);

const thumbMin = computed(() => props.sliderMin ?? props.min);
const thumbMax = computed(() => props.sliderMax ?? props.max);

/**
 * The slider always needs a concrete position, so an empty field parks the
 * thumb at the low end. The *number box* keeps the real `null` — that is what
 * lets you clear it and retype instead of the value snapping back.
 */
const sliderValue = computed({
  get: () => props.modelValue ?? thumbMin.value,
  set: (val: number) => emit("update:modelValue", val),
});

const inputId = useId();
const errorMessageId = useId();
/** Reaches the `<input>` PrimeVue renders inside its `<span>` root. */
const inputPassThrough = computed(() => ({
  pcInputText: { root: { "aria-describedby": props.errorMessage ? errorMessageId : undefined } },
}));
</script>

<template>
  <div class="flex flex-col gap-1.5">
    <div data-part="label-row" class="flex h-5 items-center justify-between gap-2">
      <span class="inline-flex min-w-0 items-center gap-1">
        <label
          :for="inputId"
          data-part="label"
          class="truncate text-sm font-medium leading-5 text-fg"
        >{{ label }}<span v-if="required" data-part="required" aria-hidden="true" class="text-negative">*</span><span v-if="required" class="sr-only">required</span></label>
        <InputInfo v-if="info" :content="info" :field-label="label" />
      </span>
      <span v-if="note" data-part="note" class="numeric shrink-0 truncate text-xs font-medium leading-5 text-fg-muted">{{ note }}</span>
    </div>
    <!--
      Slider and number box share one control row, the same 42px row every
      other field has, so a slider field sits level with the money and number
      fields beside it in a grid. The box is the plain `.ui-input` — no smaller
      padding or type size — for the same reason.
    -->
    <div data-part="control" class="flex min-h-[42px] items-center gap-3">
      <div class="min-w-0 flex-1 px-1">
        <Slider
          data-part="slider"
          v-model="sliderValue"
          :min="thumbMin"
          :max="thumbMax"
          :step="step"
          class="relative h-2 w-full cursor-pointer rounded-full bg-line"
        />
      </div>
      <div class="w-24 shrink-0">
        <InputNumber
          data-part="input"
          :input-id="inputId"
          :model-value="modelValue"
          :suffix="suffix"
          :step="step"
          :allowEmpty="true"
          :minFractionDigits="0"
          :maxFractionDigits="3"
          :invalid="!!errorMessage"
          :pt="inputPassThrough"
          :inputClass="errorMessage ? 'ui-input numeric text-right ui-input-invalid' : 'ui-input numeric text-right'"
          v-shake="errorMessage"
          @input="(e: any) => emit('update:modelValue', e.value)"
        />
      </div>
    </div>
    <p v-if="errorMessage" :id="errorMessageId" role="alert" data-part="error-message" class="text-xs text-negative">{{ errorMessage }}</p>
  </div>
</template>
