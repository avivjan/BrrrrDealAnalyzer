<script setup lang="ts">
import { computed } from 'vue'
import InlineEditValue from './InlineEditValue.vue'
import InfoTip from './InfoTip.vue'

type Theme = 'tax' | 'reserve'
type RingSize = 'primary' | 'secondary'

const props = withDefaults(
  defineProps<{
    label: string
    balance: number
    target: number
    targetLabel?: string
    theme: Theme
    secondaryLabel?: string
    secondaryValue?: number
    secondaryTip?: string
    disabled?: boolean
    size?: RingSize
    showTargetRow?: boolean
  }>(),
  {
    size: 'secondary',
    showTargetRow: true,
  },
)

const emit = defineEmits<{
  'update-balance': [value: number]
  'update-target': [value: number]
  'update-secondary': [value: number]
}>()

const RING_SIZES: Record<
  RingSize,
  { box: string; radius: number; stroke: number; balanceClass: string; labelClass: string }
> = {
  primary: {
    box: 'h-[118px] w-[118px]',
    radius: 52,
    stroke: 10,
    balanceClass: 'text-[0.95rem]',
    labelClass: 'text-[0.66rem]',
  },
  secondary: {
    box: 'h-[68px] w-[68px]',
    radius: 30,
    stroke: 7,
    balanceClass: 'text-[0.72rem]',
    labelClass: 'text-[0.58rem]',
  },
}

const ringSize = computed(() => RING_SIZES[props.size])
const circumference = computed(() => 2 * Math.PI * ringSize.value.radius)

const hasTarget = computed(() => props.target > 0)
const rawPercent = computed(() => (hasTarget.value ? props.balance / props.target : 0))
const percent = computed(() => Math.min(Math.max(rawPercent.value, 0), 1))
const isOverflow = computed(() => hasTarget.value && rawPercent.value > 1)
const isNegative = computed(() => props.balance < 0)
const dashOffset = computed(() => circumference.value * (1 - percent.value))

const gradientId = `ring-${props.theme}-${Math.random().toString(36).slice(2, 9)}`

const THEME_STYLES: Record<Theme, { from: string; to: string; label: string }> = {
  tax: { from: '#38bdf8', to: '#0ea5e9', label: 'text-sky-300' },
  reserve: { from: '#a78bfa', to: '#7c3aed', label: 'text-violet-300' },
}
const themeStyle = computed(() => THEME_STYLES[props.theme])
</script>

<template>
  <div
    class="flex min-w-0 flex-col items-center gap-1.5"
    :class="size === 'primary' ? 'flex-[1.6]' : 'flex-[0.85]'"
  >
    <div
      class="font-bold uppercase tracking-[0.08em] text-white/45"
      :class="ringSize.labelClass"
    >
      {{ label }}
    </div>

    <div class="relative" :class="ringSize.box">
      <svg viewBox="0 0 108 108" class="h-full w-full">
        <defs>
          <linearGradient :id="gradientId" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" :stop-color="themeStyle.from" />
            <stop offset="100%" :stop-color="themeStyle.to" />
          </linearGradient>
        </defs>

        <circle
          cx="54"
          cy="54"
          :r="ringSize.radius"
          fill="none"
          stroke="rgba(255,255,255,0.07)"
          :stroke-width="ringSize.stroke"
        />

        <circle
          v-if="hasTarget"
          cx="54"
          cy="54"
          :r="ringSize.radius"
          fill="none"
          :stroke="isNegative ? '#f87171' : `url(#${gradientId})`"
          :stroke-width="ringSize.stroke"
          stroke-linecap="round"
          :stroke-dasharray="circumference"
          :style="{ strokeDashoffset: dashOffset }"
          class="ring-progress"
          :class="{ 'ring-overflow-glow': isOverflow }"
          transform="rotate(-90 54 54)"
        />
        <circle
          v-else
          cx="54"
          cy="54"
          :r="ringSize.radius"
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
          class="font-extrabold text-white"
          :class="[ringSize.balanceClass, { 'text-rose-400': isNegative }]"
          @commit="(v) => emit('update-balance', Number(v))"
        />
      </div>
    </div>

    <div v-if="showTargetRow" class="flex items-center gap-1 text-[0.68rem]">
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

    <div v-if="secondaryLabel" class="flex items-center gap-1" :class="size === 'primary' ? 'text-[0.7rem]' : 'text-[0.62rem]'">
      <span class="text-white/30">{{ secondaryLabel }}</span>
      <InfoTip v-if="secondaryTip" :text="secondaryTip" />
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
