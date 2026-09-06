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
 *   (3-12% for a DSCR rate) and stay precise under the mouse, while `min`/`max`
 *   let the typed box accept anything sensible. Previously they were the same,
 *   so typing `65` into a rate box capped at 20 silently became `20`.
 *   Out-of-range values are reported by `validateDealInputs`, not rewritten.
 * - **No fraction mask** (`minFractionDigits: 0`), so `7` doesn't render as
 *   `7.00` and eat your backspaces.
 */
import InputNumber from "primevue/inputnumber";
import Slider from "primevue/slider";
import { useId } from "vue";
import { computed } from "vue";

const props = defineProps<{
  modelValue: number | null;
  label: string;
  /** Bounds for the typed box. */
  min: number;
  max: number;
  /** Bounds for the slider thumb. Defaults to `min`/`max`. */
  sliderMin?: number;
  sliderMax?: number;
  step?: number;
  suffix?: string;
  required?: boolean;
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
</script>

<template>
  <div class="flex flex-col gap-1.5">
    <div data-part="label-row" class="flex h-5 items-center justify-between gap-2">
      <label
        :for="inputId"
        data-part="label"
        class="text-sm font-medium leading-5 text-fg"
      >{{ label }}<span v-if="required" data-part="required" aria-hidden="true" class="text-negative">*</span><span v-if="required" class="sr-only">required</span></label>
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
          :min="min"
          :max="max"
          :suffix="suffix"
          :step="step"
          :allowEmpty="true"
          :minFractionDigits="0"
          :maxFractionDigits="3"
          inputClass="ui-input numeric text-right"
          @input="(e: any) => emit('update:modelValue', e.value)"
        />
      </div>
    </div>
  </div>
</template>
