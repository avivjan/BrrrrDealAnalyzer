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
}>();

const emit = defineEmits(["update:modelValue"]);

const CUSTOM = "__custom__";

const selected = computed(() => {
  const match = props.presets.find((p) => props.modelValue != null && p.value === props.modelValue);
  return match ? match.label : CUSTOM;
});

const onSelect = (event: Event) => {
  const label = (event.target as HTMLSelectElement).value;
  const preset = props.presets.find((p) => p.label === label);
  if (preset) emit("update:modelValue", preset.value);
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
      <select :id="selectId" data-part="preset" class="ui-select" :value="selected" @change="onSelect">
        <option v-for="p in presets" :key="p.label" :value="p.label">{{ p.label }} · ${{ p.value.toLocaleString() }}</option>
        <option :value="CUSTOM">Custom</option>
      </select>
    </div>
    <MoneyInput
      data-part="amount"
      :model-value="modelValue"
      label="Amount"
      :required="required"
      @update:model-value="(v: number | null) => emit('update:modelValue', v)"
    />
  </div>
</template>
