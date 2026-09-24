<script setup lang="ts">
/**
 * A money field with a quick-pick of common amounts ("3shacks $900 / 212 $1,900 / Custom").
 *
 * Picking a preset writes its amount; typing any other amount flips the select to
 * "Custom". The amount is the only value that leaves the component — the preset name is
 * a convenience, never stored.
 */
import { computed } from "vue";
import { useId } from "vue";
import MoneyInput from "./MoneyInput.vue";
import InputInfo from "./InputInfo.vue";

export interface MoneyPreset {
  label: string;
  value: number;
}

const props = defineProps<{
  modelValue: number | null;
  label: string;
  presets: MoneyPreset[];
  required?: boolean;
  info?: string;
  /** Why the amount is wrong; handed to the amount box. */
  errorMessage?: string;
}>();

const emit = defineEmits(["update:modelValue"]);

const CUSTOM_OPTION_VALUE = "__custom__";

const selectedPresetLabel = computed(() => {
  const matchingPreset = props.presets.find((preset) => props.modelValue != null && preset.value === props.modelValue);
  return matchingPreset ? matchingPreset.label : CUSTOM_OPTION_VALUE;
});

const onPresetSelected = (event: Event) => {
  const chosenLabel = (event.target as HTMLSelectElement).value;
  const chosenPreset = props.presets.find((preset) => preset.label === chosenLabel);
  if (chosenPreset) emit("update:modelValue", chosenPreset.value);
};

const selectId = useId();
</script>

<template>
  <div data-ui="preset-money" class="grid grid-cols-[minmax(0,1fr)_minmax(0,1fr)] gap-2">
    <div class="flex flex-col gap-1.5">
      <div data-part="label-row" class="flex h-5 items-center justify-between gap-2">
        <span class="inline-flex min-w-0 items-center gap-1">
          <label :for="selectId" data-part="label" class="truncate text-sm font-medium leading-5 text-fg">{{ label }}</label>
          <InputInfo v-if="info" :content="info" :field-label="label" />
        </span>
      </div>
      <select :id="selectId" data-part="preset" class="ui-select" :value="selectedPresetLabel" @change="onPresetSelected">
        <option v-for="preset in presets" :key="preset.label" :value="preset.label">{{ preset.label }} · ${{ preset.value.toLocaleString() }}</option>
        <option :value="CUSTOM_OPTION_VALUE">Custom</option>
      </select>
    </div>
    <MoneyInput
      data-part="amount"
      :model-value="modelValue"
      label="Amount"
      :required="required"
      :error-message="errorMessage"
      @update:model-value="(v: number | null) => emit('update:modelValue', v)"
    />
  </div>
</template>
