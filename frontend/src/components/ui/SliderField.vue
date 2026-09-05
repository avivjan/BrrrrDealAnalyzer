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
  <div class="flex flex-col gap-3">
    <div class="flex items-center justify-between gap-2">
      <label
        :for="inputId"
        data-part="label"
        class="text-sm font-medium text-fg"
        :class="{
          'after:content-[\'*\'] after:ml-0.5 after:text-negative': required,
        }"
      >
        {{ label }}
      </label>
      <div class="w-24">
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
          inputClass="ui-input tabular px-2 py-1 text-right text-sm"
          @input="(e: any) => emit('update:modelValue', e.value)"
        />
      </div>
    </div>
    <div class="px-1">
      <Slider
        data-part="slider"
        v-model="sliderValue"
        :min="thumbMin"
        :max="thumbMax"
        :step="step"
        class="relative h-2 w-full cursor-pointer rounded-full bg-line"
      />
    </div>
  </div>
</template>
