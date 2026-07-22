<script setup lang="ts">
import type { LLCConfiguration, PropertyStatus } from '../../types/treasury'
import PropertyCard from './PropertyCard.vue'
import InlineEditValue from './InlineEditValue.vue'
import KebabMenu from './KebabMenu.vue'

defineProps<{
  llc: LLCConfiguration
  properties: PropertyStatus[]
  allLlcs: LLCConfiguration[]
  disabled?: boolean
}>()

const emit = defineEmits<{
  'patch-llc': [field: 'llc_name' | 'checking_redline_buffer', value: string | number]
  'delete-llc': []
  'patch-property': [propertyId: string, field: string, value: number | boolean | string]
  'delete-property': [propertyId: string]
  'open-cash-flow': [property: PropertyStatus]
  'open-settings': [property: PropertyStatus]
  'move-property': [propertyId: string, llcId: string]
}>()
</script>

<template>
  <section class="llc-section">
    <header class="llc-header">
      <div class="min-w-0 flex-1">
        <div class="flex items-center gap-2">
          <i class="pi pi-building text-indigo-400"></i>
          <InlineEditValue
            :model-value="llc.llc_name"
            :disabled="disabled"
            class="text-lg font-extrabold text-white"
            @commit="(v) => emit('patch-llc', 'llc_name', v)"
          />
        </div>
        <code class="ml-6 text-[0.65rem] text-white/25">{{ llc.llc_id }}</code>
      </div>

      <div class="flex items-center gap-2">
        <div class="redline-chip">
          <i class="pi pi-shield text-[0.65rem]"></i>
          <span class="chip-label">Redline Buffer</span>
          <InlineEditValue
            :model-value="llc.checking_redline_buffer"
            type="number"
            currency
            :decimals="2"
            :disabled="disabled"
            class="font-bold text-amber-300"
            @commit="(v) => emit('patch-llc', 'checking_redline_buffer', v)"
          />
        </div>

        <div class="count-chip">
          <i class="pi pi-home text-[0.65rem]"></i>
          {{ properties.length }} {{ properties.length === 1 ? 'property' : 'properties' }}
        </div>

        <KebabMenu>
          <template #default="{ close }">
            <button
              type="button"
              class="kebab-item kebab-danger"
              @click="emit('delete-llc'); close()"
            >
              <i class="pi pi-trash"></i> Delete LLC
            </button>
          </template>
        </KebabMenu>
      </div>
    </header>

    <div v-if="properties.length === 0" class="empty-state">
      No properties attached yet — use <strong>+ Add Property</strong> above to nest one here.
    </div>
    <div v-else class="property-grid">
      <PropertyCard
        v-for="prop in properties"
        :key="prop.property_id"
        :property="prop"
        :llcs="allLlcs"
        :disabled="disabled"
        @patch="(field, value) => emit('patch-property', prop.property_id, field, value)"
        @delete="emit('delete-property', prop.property_id)"
        @open-cash-flow="emit('open-cash-flow', prop)"
        @open-settings="emit('open-settings', prop)"
        @move-llc="(llcId) => emit('move-property', prop.property_id, llcId)"
      />
    </div>
  </section>
</template>

<style scoped>
.llc-section {
  border-radius: 1.25rem;
  background: rgba(15, 23, 42, 0.65);
  border: 1px solid rgba(99, 102, 241, 0.18);
  padding: 1.1rem 1.2rem 1.35rem;
  box-shadow: 0 24px 60px -30px rgba(0, 0, 0, 0.7);
}

.llc-header {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.75rem;
  margin-bottom: 1rem;
  padding-bottom: 0.85rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

.redline-chip,
.count-chip {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.4rem 0.7rem;
  border-radius: 999px;
  font-size: 0.74rem;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.08);
  color: rgba(255, 255, 255, 0.55);
  white-space: nowrap;
}

.chip-label {
  color: rgba(255, 255, 255, 0.4);
}

.property-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 1rem;
}

.empty-state {
  border: 1px dashed rgba(255, 255, 255, 0.12);
  border-radius: 0.9rem;
  padding: 1.5rem;
  text-align: center;
  font-size: 0.82rem;
  color: rgba(255, 255, 255, 0.35);
}

.kebab-item {
  display: flex;
  width: 100%;
  align-items: center;
  gap: 0.5rem;
  border-radius: 0.5rem;
  padding: 0.5rem 0.6rem;
  font-size: 0.78rem;
  font-weight: 500;
  background: transparent;
  border: none;
  cursor: pointer;
  text-align: left;
  transition: background-color 0.12s ease;
}

.kebab-item:hover {
  background: rgba(255, 255, 255, 0.06);
}

.kebab-danger {
  color: #fb7185;
}
</style>
