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
</script>

<template>
  <div class="flex flex-col gap-3">
    <div class="flex justify-between items-center">
      <label
        class="text-sm font-medium text-gray-700"
        :class="{
          'after:content-[\'*\'] after:ml-0.5 after:text-red-500': required,
        }"
      >
        {{ label }}
      </label>
      <div class="w-24">
        <InputNumber
          :model-value="modelValue"
          :min="min"
          :max="max"
          :suffix="suffix"
          :step="step"
          :allowEmpty="true"
          :minFractionDigits="0"
          :maxFractionDigits="3"
          inputClass="w-full text-right bg-white border border-gray-300 rounded-lg px-2 py-1 text-sm text-gray-900 focus:outline-none focus:ring-1 focus:ring-blue-500"
          @input="(e: any) => emit('update:modelValue', e.value)"
        />
      </div>
    </div>
    <div class="px-1">
      <Slider
        v-model="sliderValue"
        :min="thumbMin"
        :max="thumbMax"
        :step="step"
        class="w-full h-2 bg-gray-200 rounded-full cursor-pointer relative"
        :pt="{
          range: {
            class: 'bg-blue-500 h-full rounded-full absolute top-0 left-0',
          },
          handle: {
            class:
              'bg-white border-2 border-blue-500 w-5 h-5 rounded-full absolute top-1/2 -mt-2.5 -ml-2.5 shadow-md hover:scale-110 transition-transform focus:outline-none focus:ring-2 focus:ring-blue-300',
          },
        }"
      />
    </div>
  </div>
</template>
