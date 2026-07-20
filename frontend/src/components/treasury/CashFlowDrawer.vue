<script setup lang="ts">
import { ref, computed } from 'vue'
import type { PropertyStatus, PropertyCashFlowHistory } from '../../types/treasury'
import InlineEditValue from './InlineEditValue.vue'

const props = defineProps<{
  open: boolean
  property: PropertyStatus | null
  history: PropertyCashFlowHistory[]
}>()

const emit = defineEmits<{
  close: []
  'patch-row': [historyId: string, field: 'month_year' | 'monthly_cash_flow' | 'cumulative_cash_flow', value: string | number]
  'delete-row': [historyId: string]
  'add-row': [monthYear: string]
}>()

const newMonth = ref('')

const rows = computed(() =>
  [...props.history].sort((a, b) => a.month_year.localeCompare(b.month_year)),
)

function addRow() {
  const trimmed = newMonth.value.trim()
  if (!/^\d{4}-(0[1-9]|1[0-2])$/.test(trimmed)) return
  emit('add-row', trimmed)
  newMonth.value = ''
}
</script>

<template>
  <Transition name="drawer-fade">
    <div v-if="open" class="fixed inset-0 z-[60] bg-black/55 backdrop-blur-sm" @click.self="emit('close')">
      <Transition name="drawer-slide" appear>
        <aside v-if="open" class="drawer-panel">
          <header class="drawer-head">
            <div>
              <h3 class="text-sm font-bold text-white">Cash Flow History</h3>
              <p class="text-[0.72rem] text-white/40">{{ property?.property_id }}</p>
            </div>
            <button class="close-btn" @click="emit('close')"><i class="pi pi-times"></i></button>
          </header>

          <div class="drawer-add">
            <input
              v-model="newMonth"
              type="text"
              placeholder="YYYY-MM"
              class="month-input"
              @keydown.enter="addRow"
            />
            <button class="add-btn" @click="addRow"><i class="pi pi-plus"></i> Add Snapshot</button>
          </div>

          <div class="drawer-body">
            <div v-if="rows.length === 0" class="empty-state">No snapshots recorded yet.</div>
            <table v-else class="cf-table">
              <thead>
                <tr>
                  <th>Month</th>
                  <th>Monthly</th>
                  <th>Cumulative</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="row in rows" :key="row.history_id">
                  <td>
                    <InlineEditValue
                      :model-value="row.month_year"
                      class="font-semibold text-white/80"
                      @commit="(v) => emit('patch-row', row.history_id, 'month_year', v)"
                    />
                  </td>
                  <td>
                    <InlineEditValue
                      :model-value="row.monthly_cash_flow"
                      type="number"
                      currency
                      :decimals="0"
                      :class="row.monthly_cash_flow < 0 ? 'text-rose-400' : 'text-emerald-300'"
                      class="font-semibold"
                      @commit="(v) => emit('patch-row', row.history_id, 'monthly_cash_flow', v)"
                    />
                  </td>
                  <td>
                    <InlineEditValue
                      :model-value="row.cumulative_cash_flow"
                      type="number"
                      currency
                      :decimals="0"
                      class="font-semibold text-white/70"
                      @commit="(v) => emit('patch-row', row.history_id, 'cumulative_cash_flow', v)"
                    />
                  </td>
                  <td>
                    <button class="row-delete" @click="emit('delete-row', row.history_id)">
                      <i class="pi pi-trash"></i>
                    </button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </aside>
      </Transition>
    </div>
  </Transition>
</template>

<style scoped>
.drawer-panel {
  position: absolute;
  top: 0;
  right: 0;
  height: 100%;
  width: min(420px, 100%);
  background: #0b0f1a;
  border-left: 1px solid rgba(255, 255, 255, 0.08);
  box-shadow: -30px 0 60px -30px rgba(0, 0, 0, 0.8);
  display: flex;
  flex-direction: column;
}

.drawer-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1rem 1.15rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

.close-btn {
  color: rgba(255, 255, 255, 0.4);
  background: transparent;
  border: none;
  cursor: pointer;
  padding: 0.25rem;
}

.close-btn:hover {
  color: white;
}

.drawer-add {
  display: flex;
  gap: 0.5rem;
  padding: 0.85rem 1.15rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

.month-input {
  flex: 1;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 0.55rem;
  padding: 0.45rem 0.6rem;
  font-size: 0.82rem;
  color: white;
  outline: none;
}

.add-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.45rem 0.75rem;
  border-radius: 0.55rem;
  background: linear-gradient(135deg, #6366f1, #7c3aed);
  color: white;
  font-size: 0.78rem;
  font-weight: 700;
  border: none;
  cursor: pointer;
  white-space: nowrap;
}

.drawer-body {
  flex: 1;
  overflow-y: auto;
  padding: 0.5rem 1.15rem 1.5rem;
}

.empty-state {
  padding: 2rem 0;
  text-align: center;
  font-size: 0.82rem;
  color: rgba(255, 255, 255, 0.3);
}

.cf-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.8rem;
}

.cf-table thead th {
  text-align: left;
  padding: 0.5rem 0.4rem;
  font-size: 0.65rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: rgba(255, 255, 255, 0.35);
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.cf-table tbody td {
  padding: 0.55rem 0.4rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
}

.row-delete {
  color: rgba(255, 255, 255, 0.3);
  background: transparent;
  border: none;
  cursor: pointer;
  padding: 0.2rem;
  transition: color 0.15s ease;
}

.row-delete:hover {
  color: #fb7185;
}

.drawer-fade-enter-active,
.drawer-fade-leave-active {
  transition: opacity 0.25s ease;
}

.drawer-fade-enter-from,
.drawer-fade-leave-to {
  opacity: 0;
}

.drawer-slide-enter-active,
.drawer-slide-leave-active {
  transition: transform 0.28s cubic-bezier(0.22, 1, 0.36, 1);
}

.drawer-slide-enter-from,
.drawer-slide-leave-to {
  transform: translateX(100%);
}
</style>
