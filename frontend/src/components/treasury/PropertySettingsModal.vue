<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { PropertyStatus } from '../../types/treasury'
import InlineEditValue from './InlineEditValue.vue'
import ToggleSwitch from './ToggleSwitch.vue'

const props = defineProps<{
  open: boolean
  property: PropertyStatus | null
  disabled?: boolean
}>()

const emit = defineEmits<{
  close: []
  patch: [field: string, value: number | boolean]
}>()

const reservePctDraft = ref(0)

watch(
  () => [props.property?.base_rent_target, props.property?.target_reserve_allocation] as const,
  ([rent, reserve]) => {
    const monthlyRent = Number(rent ?? 0)
    const monthlyReserve = Number(reserve ?? 0)
    reservePctDraft.value =
      monthlyRent > 0 ? Math.round((monthlyReserve / monthlyRent) * 10000) / 100 : 0
  },
  { immediate: true },
)

const reserveMonthlyPreview = computed(() => {
  const rent = Number(props.property?.base_rent_target ?? 0)
  return Math.round((rent * reservePctDraft.value) / 100)
})

function patch(field: string, value: number | boolean) {
  emit('patch', field, value)
}

function onReservePctCommit(value: number | string) {
  const pct = Number(value)
  reservePctDraft.value = pct
  const rent = Number(props.property?.base_rent_target ?? 0)
  const monthlyReserve = Math.round((rent * pct) / 100)
  patch('target_reserve_allocation', monthlyReserve)
}

function onMonthlyRentCommit(value: number | string) {
  const rent = Number(value)
  patch('base_rent_target', rent)
  const monthlyReserve = Math.round((rent * reservePctDraft.value) / 100)
  patch('target_reserve_allocation', monthlyReserve)
}
</script>

<template>
  <Transition name="modal-fade">
    <div v-if="open" class="modal-backdrop" @click.self="emit('close')">
      <Transition name="modal-scale" appear>
        <div v-if="open && property" class="modal-panel">
          <header class="modal-head">
            <div>
              <h3 class="text-sm font-bold text-white">Property Settings</h3>
              <p class="text-[0.72rem] text-white/40">{{ property.property_name }}</p>
            </div>
            <button class="close-btn" type="button" @click="emit('close')">
              <i class="pi pi-times"></i>
            </button>
          </header>

          <div class="modal-body">
            <section class="settings-group">
              <h4 class="group-title">Monthly Allocations</h4>
              <p class="group-hint">
                Set the expected monthly rent and how much to allocate to tax and reserve each cycle.
              </p>

              <label class="field-row">
                <span class="field-label">Monthly Rent</span>
                <InlineEditValue
                  :model-value="property.base_rent_target"
                  type="number"
                  currency
                  :decimals="0"
                  :disabled="disabled"
                  class="field-value text-emerald-300"
                  @commit="onMonthlyRentCommit"
                />
              </label>

              <label class="field-row">
                <span class="field-label">Monthly Tax</span>
                <InlineEditValue
                  :model-value="property.target_tax_allocation"
                  type="number"
                  currency
                  :decimals="0"
                  :disabled="disabled"
                  class="field-value text-sky-300"
                  @commit="(v) => patch('target_tax_allocation', Number(v))"
                />
              </label>

              <label class="field-row">
                <span class="field-label">Reserve (% of Rent)</span>
                <div class="field-inline">
                  <InlineEditValue
                    :model-value="reservePctDraft"
                    type="number"
                    :decimals="1"
                    :disabled="disabled"
                    class="field-value text-violet-300"
                    @commit="onReservePctCommit"
                  />
                  <span class="field-note">≈ ${{ reserveMonthlyPreview.toLocaleString() }}/mo</span>
                </div>
              </label>
            </section>

            <section class="settings-group">
              <h4 class="group-title">Reserve Controls</h4>

              <label class="field-row">
                <span class="field-label">Reserve Cap</span>
                <InlineEditValue
                  :model-value="property.reserve_bucket_cap"
                  type="number"
                  currency
                  :decimals="0"
                  :disabled="disabled"
                  class="field-value text-violet-300"
                  @commit="(v) => patch('reserve_bucket_cap', Number(v))"
                />
              </label>

              <div class="toggle-row">
                <div>
                  <span class="field-label">Double Reserve On Recovery</span>
                  <p class="field-hint">When enabled, reserve contributions double until the bucket recovers.</p>
                </div>
                <ToggleSwitch
                  :model-value="property.double_reserve_on_recovery"
                  :disabled="disabled"
                  @update:model-value="(v) => patch('double_reserve_on_recovery', v)"
                />
              </div>
            </section>
          </div>
        </div>
      </Transition>
    </div>
  </Transition>
</template>

<style scoped>
.modal-backdrop {
  position: fixed;
  inset: 0;
  z-index: 70;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1rem;
  background: rgba(0, 0, 0, 0.6);
  backdrop-filter: blur(4px);
}

.modal-panel {
  width: min(100%, 420px);
  border-radius: 1rem;
  background: linear-gradient(160deg, rgba(30, 41, 59, 0.98), rgba(15, 23, 42, 0.98));
  border: 1px solid rgba(255, 255, 255, 0.1);
  box-shadow: 0 30px 70px -25px rgba(0, 0, 0, 0.75);
}

.modal-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.75rem;
  padding: 1rem 1.1rem 0.85rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

.close-btn {
  width: 2rem;
  height: 2rem;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 0.55rem;
  background: rgba(255, 255, 255, 0.06);
  color: rgba(255, 255, 255, 0.65);
  border: none;
  cursor: pointer;
}

.close-btn:hover {
  background: rgba(255, 255, 255, 0.12);
  color: white;
}

.modal-body {
  padding: 0.85rem 1.1rem 1.1rem;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.settings-group {
  display: flex;
  flex-direction: column;
  gap: 0.55rem;
}

.group-title {
  margin: 0;
  font-size: 0.78rem;
  font-weight: 800;
  color: rgba(255, 255, 255, 0.85);
  letter-spacing: 0.02em;
}

.group-hint {
  margin: 0 0 0.25rem;
  font-size: 0.68rem;
  color: rgba(255, 255, 255, 0.35);
  line-height: 1.4;
}

.field-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  padding: 0.55rem 0.65rem;
  border-radius: 0.65rem;
  background: rgba(0, 0, 0, 0.2);
  border: 1px solid rgba(255, 255, 255, 0.05);
}

.field-label {
  font-size: 0.74rem;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.55);
}

.field-value {
  font-size: 0.86rem;
  font-weight: 700;
}

.field-inline {
  display: flex;
  align-items: center;
  gap: 0.45rem;
}

.field-note {
  font-size: 0.68rem;
  color: rgba(255, 255, 255, 0.35);
  white-space: nowrap;
}

.toggle-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  padding: 0.65rem;
  border-radius: 0.65rem;
  background: rgba(0, 0, 0, 0.2);
  border: 1px solid rgba(255, 255, 255, 0.05);
}

.field-hint {
  margin: 0.2rem 0 0;
  font-size: 0.65rem;
  color: rgba(255, 255, 255, 0.32);
  line-height: 1.35;
  max-width: 240px;
}

.modal-fade-enter-active,
.modal-fade-leave-active {
  transition: opacity 0.2s ease;
}

.modal-fade-enter-from,
.modal-fade-leave-to {
  opacity: 0;
}

.modal-scale-enter-active,
.modal-scale-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}

.modal-scale-enter-from,
.modal-scale-leave-to {
  opacity: 0;
  transform: scale(0.96) translateY(8px);
}
</style>
