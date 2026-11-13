<script setup lang="ts">
/** One figure of a construction account card that is shown, not edited, with its one-line "how this is computed". */
import { formatMoney } from '../../../utils/money'

withDefaults(defineProps<{
  testid: string
  label: string
  value: number | string | null | undefined
  explanation?: string
  tone?: 'neutral' | 'positive' | 'negative' | 'warning'
  emphasis?: boolean
}>(), { explanation: undefined, tone: 'neutral', emphasis: false })

const TONE_CLASS = { neutral: 'text-fg', positive: 'text-positive', negative: 'text-negative', warning: 'text-warning' } as const

function shown(value: number | string | null | undefined): string {
  if (value == null || value === '') return '—'
  return typeof value === 'number' ? formatMoney(value) : value
}
</script>

<template>
  <div class="flex flex-col gap-0.5">
    <div class="flex items-center justify-between gap-3">
      <span class="text-sm text-fg-muted">{{ label }}</span>
      <span :data-testid="testid" class="numeric text-right" :class="[TONE_CLASS[tone], emphasis ? 'text-base font-bold' : 'text-sm font-semibold']">
        {{ shown(value) }}
      </span>
    </div>
    <p v-if="explanation" class="text-xs text-fg-muted">{{ explanation }}</p>
    <slot />
  </div>
</template>
