<script setup lang="ts">
import { computed } from 'vue'
import InlineEditValue from './InlineEditValue.vue'

type Theme = 'tax' | 'reserve'

const props = defineProps<{
  label: string
  balance: number
  target: number
  targetLabel?: string
  theme: Theme
  secondaryLabel?: string
  secondaryValue?: number
  disabled?: boolean
}>()

const emit = defineEmits<{
  'update-balance': [value: number]
  'update-target': [value: number]
  'update-secondary': [value: number]
}>()

const RADIUS = 46
const CIRCUMFERENCE = 2 * Math.PI * RADIUS

const hasTarget = computed(() => props.target > 0)
const rawPercent = computed(() => (hasTarget.value ? props.balance / props.target : 0))
const percent = computed(() => Math.min(Math.max(rawPercent.value, 0), 1))
const isOverflow = computed(() => hasTarget.value && rawPercent.value > 1)
const isNegative = computed(() => props.balance < 0)
const dashOffset = computed(() => CIRCUMFERENCE * (1 - percent.value))

const gradientId = `ring-${props.theme}-${Math.random().toString(36).slice(2, 9)}`

const THEME_STYLES: Record<Theme, { from: string; to: string; label: string }> = {
  tax: { from: '#38bdf8', to: '#0ea5e9', label: 'text-sky-300' },
  reserve: { from: '#a78bfa', to: '#7c3aed', label: 'text-violet-300' },
}
const themeStyle = computed(() => THEME_STYLES[props.theme])
</script>

<template>
  <div class="flex flex-1 min-w-0 flex-col items-center gap-1.5">
    <div class="text-[0.62rem] font-bold uppercase tracking-[0.08em] text-white/45">
      {{ label }}
    </div>

    <div class="relative h-[86px] w-[86px]">
      <svg viewBox="0 0 108 108" class="h-full w-full">
        <defs>
          <linearGradient :id="gradientId" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" :stop-color="themeStyle.from" />
            <stop offset="100%" :stop-color="themeStyle.to" />
          </linearGradient>
        </defs>

        <circle cx="54" cy="54" :r="RADIUS" fill="none" stroke="rgba(255,255,255,0.07)" stroke-width="9" />

        <circle
          v-if="hasTarget"
          cx="54"
          cy="54"
          :r="RADIUS"
          fill="none"
          :stroke="isNegative ? '#f87171' : `url(#${gradientId})`"
          stroke-width="9"
          stroke-linecap="round"
          :stroke-dasharray="CIRCUMFERENCE"
          :style="{ strokeDashoffset: dashOffset }"
          class="ring-progress"
          :class="{ 'ring-overflow-glow': isOverflow }"
          transform="rotate(-90 54 54)"
        />
        <circle
          v-else
          cx="54"
          cy="54"
          :r="RADIUS"
          fill="none"
          stroke="rgba(255,255,255,0.2)"
          stroke-width="4"
          stroke-dasharray="4 6"
        />
      </svg>

      <div class="absolute inset-0 flex flex-col items-center justify-center gap-0">
        <InlineEditValue
          :model-value="balance"
          type="number"
          currency
          :decimals="0"
          :disabled="disabled"
          class="text-[0.82rem] font-extrabold text-white"
          :class="{ 'text-rose-400': isNegative }"
          @commit="(v) => emit('update-balance', Number(v))"
        />
      </div>
    </div>

    <div class="flex items-center gap-1 text-[0.68rem]">
      <span class="text-white/40">{{ targetLabel ?? 'Target' }}</span>
      <InlineEditValue
        :model-value="target"
        type="number"
        currency
        :decimals="0"
        treat-zero-as-unset
        :disabled="disabled"
        class="font-semibold"
        :class="themeStyle.label"
        @commit="(v) => emit('update-target', Number(v))"
      />
    </div>

    <div v-if="secondaryLabel" class="flex items-center gap-1 text-[0.66rem]">
      <span class="text-white/30">{{ secondaryLabel }}</span>
      <InlineEditValue
        :model-value="secondaryValue ?? 0"
        type="number"
        currency
        :decimals="0"
        :disabled="disabled"
        class="font-medium text-white/70"
        @commit="(v) => emit('update-secondary', Number(v))"
      />
    </div>
  </div>
</template>

<style scoped>
.ring-progress {
  transition: stroke-dashoffset 0.9s cubic-bezier(0.22, 1, 0.36, 1);
}

.ring-overflow-glow {
  filter: drop-shadow(0 0 6px rgba(167, 139, 250, 0.75));
}
</style>
