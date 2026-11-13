<script setup lang="ts">
/**
 * One editable figure of a construction account card (tasks/todo/ConstructionAccountPerRehab.md): it reads as a
 * button; a tap opens a box seeded with the value; Enter (or leaving the box) asks to save, Escape cancels. The parent
 * runs the save, which opens the timeline prompt when the figure moves the timeline. Modelled on InlineAmountEditor.
 */
import { nextTick, ref } from 'vue'

import { formatMoney } from '../../../utils/money'

const props = withDefaults(defineProps<{
  /** The figure's hook: `ca.<deal>.<figure>`; the box is `<testid>.input`. */
  testid: string
  label: string
  value: number
  unit?: 'dollars' | 'percent'
  /** One line under the figure: how it is computed, or what it does. */
  explanation?: string
  isSaving?: boolean
}>(), { unit: 'dollars', explanation: undefined, isSaving: false })

const emit = defineEmits<{ (e: 'save', newValue: number): void }>()

const isEditing = ref(false)
const typedValue = ref('')
const box = ref<HTMLInputElement | null>(null)

async function startEditing() {
  typedValue.value = String(props.value)
  isEditing.value = true
  await nextTick()
  box.value?.select()
}

function save() {
  if (!isEditing.value) return
  isEditing.value = false
  const typed = Number(typedValue.value)
  if (!Number.isFinite(typed) || typed < 0) return
  const newValue = Math.round(typed * 100) / 100
  if (newValue !== props.value) emit('save', newValue)
}

function shown(value: number): string {
  return props.unit === 'percent' ? `${value}%` : formatMoney(value)
}
</script>

<template>
  <div class="flex flex-col gap-0.5">
    <div class="flex items-center justify-between gap-3">
      <span class="text-sm text-fg-muted">{{ label }}</span>
      <input
        v-if="isEditing"
        ref="box"
        v-model="typedValue"
        :data-testid="`${testid}.input`"
        :aria-label="`${label}, in ${unit === 'percent' ? 'percent' : 'dollars'}`"
        type="number"
        inputmode="decimal"
        min="0"
        :step="unit === 'percent' ? '0.01' : '1'"
        class="ui-input numeric h-8 w-32 touch:h-11 text-right text-sm"
        @keydown.enter.prevent="save"
        @keydown.escape.prevent="isEditing = false"
        @blur="save"
      />
      <button
        v-else
        type="button"
        :data-testid="testid"
        :disabled="isSaving"
        class="numeric rounded-ctl px-1.5 py-0.5 text-sm font-semibold text-fg underline decoration-dotted underline-offset-4 hover:bg-surface-3 disabled:opacity-60"
        :title="`Tap to change ${label.toLowerCase()}`"
        @click="startEditing"
      >
        {{ shown(value) }}<i class="pi pi-pencil ml-1.5 text-[10px] text-fg-muted" aria-hidden="true"></i>
      </button>
    </div>
    <p v-if="explanation" class="text-xs text-fg-muted">{{ explanation }}</p>
  </div>
</template>
