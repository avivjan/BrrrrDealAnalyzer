<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useTreasuryStore } from '../stores/treasuryStore'
import type { PropertyStatus } from '../types/treasury'
import LlcSection from '../components/treasury/LlcSection.vue'
import AuditLogTable from '../components/treasury/AuditLogTable.vue'
import AddLlcModal from '../components/treasury/AddLlcModal.vue'
import AddPropertyModal from '../components/treasury/AddPropertyModal.vue'
import CashFlowDrawer from '../components/treasury/CashFlowDrawer.vue'

const router = useRouter()
const store = useTreasuryStore()

const toast = ref('')
const toastVisible = ref(false)
let toastTimer: ReturnType<typeof setTimeout> | undefined

const addLlcOpen = ref(false)
const addPropertyOpen = ref(false)
const cashFlowProperty = ref<PropertyStatus | null>(null)

const llcGroups = computed(() =>
  store.llcs.map((llc) => ({
    llc,
    properties: store.properties.filter((p) => p.llc_id === llc.llc_id),
  })),
)

const totalReserveBalance = computed(() =>
  store.properties.reduce((sum, p) => sum + Number(p.reserve_bucket_balance), 0),
)
const totalDebt = computed(() =>
  store.properties.reduce((sum, p) => sum + Number(p.reserve_debt), 0),
)

const cashFlowHistoryForProperty = computed(() =>
  cashFlowProperty.value
    ? store.cashFlowHistory.filter((row) => row.property_id === cashFlowProperty.value!.property_id)
    : [],
)

onMounted(async () => {
  try {
    await store.fetchAll()
  } catch {
    showToast(store.error ?? 'Failed to load treasury data')
  }
})

function showToast(message: string) {
  toast.value = message
  toastVisible.value = true
  clearTimeout(toastTimer)
  toastTimer = setTimeout(() => {
    toastVisible.value = false
  }, 3200)
}

function formatCurrency(value: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 0,
  }).format(value)
}

async function onPatchLlc(llcId: string, field: 'llc_name' | 'checking_redline_buffer', value: string | number) {
  try {
    await store.patchLlc(llcId, { [field]: value } as never)
  } catch {
    showToast(`Failed to save ${field}`)
  }
}

async function onDeleteLlc(llcId: string) {
  if (!window.confirm('Delete this LLC and every property/history nested inside it?')) return
  try {
    await store.removeLlc(llcId)
    showToast('LLC deleted')
  } catch {
    showToast('Failed to delete LLC')
  }
}

async function onPatchProperty(propertyId: string, field: string, value: number | boolean | string) {
  try {
    await store.patchProperty(propertyId, { [field]: value } as never)
  } catch {
    showToast(`Failed to save ${field}`)
  }
}

async function onDeleteProperty(propertyId: string) {
  if (!window.confirm('Delete this property and its cash-flow history?')) return
  try {
    await store.removeProperty(propertyId)
    if (cashFlowProperty.value?.property_id === propertyId) cashFlowProperty.value = null
    showToast('Property deleted')
  } catch {
    showToast('Failed to delete property')
  }
}

async function onMoveProperty(propertyId: string, llcId: string) {
  try {
    await store.patchProperty(propertyId, { llc_id: llcId })
    showToast('Property re-parented to new LLC')
  } catch {
    showToast('Failed to move property')
  }
}

function onOpenCashFlow(property: PropertyStatus) {
  cashFlowProperty.value = property
}

async function onPatchCashFlowRow(
  historyId: string,
  field: 'month_year' | 'monthly_cash_flow' | 'cumulative_cash_flow',
  value: string | number,
) {
  try {
    await store.patchCashFlow(historyId, { [field]: value } as never)
  } catch {
    showToast(`Failed to save ${field}`)
  }
}

async function onDeleteCashFlowRow(historyId: string) {
  if (!window.confirm('Delete this snapshot?')) return
  try {
    await store.removeCashFlow(historyId)
  } catch {
    showToast('Failed to delete snapshot')
  }
}

async function onAddCashFlowRow(monthYear: string) {
  if (!cashFlowProperty.value) return
  try {
    await store.createCashFlow({ property_id: cashFlowProperty.value.property_id, month_year: monthYear })
  } catch {
    showToast('Failed to create snapshot')
  }
}

async function onPatchTransaction(transactionId: string, field: string, value: number | boolean | string | null) {
  try {
    await store.patchTransaction(transactionId, { [field]: value } as never)
  } catch {
    showToast(`Failed to save ${field}`)
  }
}

async function onDeleteTransaction(transactionId: string) {
  if (!window.confirm('Delete this transaction?')) return
  try {
    await store.removeTransaction(transactionId)
  } catch {
    showToast('Failed to delete transaction')
  }
}

async function onAddTransaction() {
  if (store.properties.length === 0) {
    showToast('Create a property first')
    return
  }
  try {
    await store.createTransaction({
      property_id: store.properties[0]?.property_id ?? null,
      amount: 0,
      description: 'Manual entry',
      timestamp: new Date().toISOString(),
      transaction_type: 'Rent',
    })
  } catch {
    showToast('Failed to create transaction')
  }
}

async function submitAddLlc(payload: { llc_name: string; checking_redline_buffer: number }) {
  try {
    await store.createLlc(payload)
    addLlcOpen.value = false
    showToast('LLC created')
  } catch {
    showToast('Failed to create LLC')
  }
}

async function submitAddProperty(payload: { property_name: string; llc_id: string }) {
  try {
    await store.createProperty(payload)
    addPropertyOpen.value = false
    showToast('Property created')
  } catch {
    showToast('Failed to create property')
  }
}

</script>

<template>
  <div class="treasury-page">
    <header class="page-header">
      <div class="flex items-center gap-3">
        <button class="back-btn" title="Back" @click="router.push('/')">
          <i class="pi pi-arrow-left"></i>
        </button>
        <div>
          <h1 class="page-title">Reserve &amp; Treasury</h1>
          <p class="page-subtitle">Control room for every bucket, buffer, and flag</p>
        </div>
      </div>

      <div class="header-stats">
        <div class="stat-chip">
          <span class="stat-chip-label">LLCs</span>
          <span class="stat-chip-value text-white">{{ store.llcs.length }}</span>
        </div>
        <div class="stat-chip">
          <span class="stat-chip-label">Properties</span>
          <span class="stat-chip-value text-white">{{ store.properties.length }}</span>
        </div>
        <div class="stat-chip">
          <span class="stat-chip-label">Reserve Balance</span>
          <span class="stat-chip-value text-violet-300">{{ formatCurrency(totalReserveBalance) }}</span>
        </div>
        <div class="stat-chip">
          <span class="stat-chip-label">Total Debt</span>
          <span class="stat-chip-value" :class="totalDebt > 0 ? 'text-rose-400' : 'text-white/40'">
            {{ formatCurrency(totalDebt) }}
          </span>
        </div>
      </div>

      <div class="header-actions">
        <button class="icon-btn" :disabled="store.loading" title="Refresh" @click="store.fetchAll()">
          <i class="pi pi-refresh" :class="{ spin: store.loading }"></i>
        </button>
        <button class="action-btn action-btn-llc" @click="addLlcOpen = true">
          <i class="pi pi-plus"></i> Add LLC
        </button>
        <button class="action-btn action-btn-property" @click="addPropertyOpen = true">
          <i class="pi pi-plus"></i> Add Property
        </button>
      </div>
    </header>

    <main class="page-body">
      <div v-if="store.llcs.length === 0" class="landing-empty">
        <i class="pi pi-building"></i>
        <p>No LLCs yet — click <strong>+ Add LLC</strong> to stand up your first treasury container.</p>
      </div>

      <LlcSection
        v-for="group in llcGroups"
        :key="group.llc.llc_id"
        :llc="group.llc"
        :properties="group.properties"
        :all-llcs="store.llcs"
        :disabled="store.loading"
        @patch-llc="(field, value) => onPatchLlc(group.llc.llc_id, field, value)"
        @delete-llc="onDeleteLlc(group.llc.llc_id)"
        @patch-property="onPatchProperty"
        @delete-property="onDeleteProperty"
        @open-cash-flow="onOpenCashFlow"
        @move-property="onMoveProperty"
      />

      <AuditLogTable
        :transactions="store.transactions"
        :properties="store.properties"
        :llcs="store.llcs"
        :disabled="store.loading"
        @patch="onPatchTransaction"
        @delete="onDeleteTransaction"
        @add="onAddTransaction"
      />
    </main>

    <AddLlcModal :is-open="addLlcOpen" @close="addLlcOpen = false" @submit="submitAddLlc" />
    <AddPropertyModal
      :is-open="addPropertyOpen"
      :llcs="store.llcs"
      @close="addPropertyOpen = false"
      @submit="submitAddProperty"
    />
    <CashFlowDrawer
      :open="!!cashFlowProperty"
      :property="cashFlowProperty"
      :history="cashFlowHistoryForProperty"
      @close="cashFlowProperty = null"
      @patch-row="onPatchCashFlowRow"
      @delete-row="onDeleteCashFlowRow"
      @add-row="onAddCashFlowRow"
    />

    <Transition name="toast">
      <div v-if="toastVisible" class="toast">{{ toast }}</div>
    </Transition>
  </div>
</template>

<style scoped>
.treasury-page {
  min-height: 100vh;
  background: linear-gradient(160deg, #020617 0%, #0b0f1f 45%, #0f172a 100%);
  color: #e2e8f0;
}

.page-header {
  position: sticky;
  top: 0;
  z-index: 30;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding: 0.9rem 1.5rem;
  background: rgba(2, 6, 23, 0.85);
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  backdrop-filter: blur(10px);
}

.back-btn,
.icon-btn {
  width: 2.25rem;
  height: 2.25rem;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 0.65rem;
  background: rgba(255, 255, 255, 0.06);
  color: rgba(255, 255, 255, 0.7);
  border: none;
  cursor: pointer;
  transition: background-color 0.15s ease, color 0.15s ease;
}

.back-btn:hover,
.icon-btn:hover {
  background: rgba(255, 255, 255, 0.12);
  color: white;
}

.icon-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.page-title {
  margin: 0;
  font-size: 1.2rem;
  font-weight: 800;
  color: white;
  letter-spacing: -0.01em;
}

.page-subtitle {
  margin: 0.05rem 0 0;
  font-size: 0.75rem;
  color: rgba(255, 255, 255, 0.4);
}

.header-stats {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  flex-wrap: wrap;
}

.stat-chip {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  padding: 0.4rem 0.75rem;
  border-radius: 0.7rem;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.07);
  min-width: 88px;
}

.stat-chip-label {
  font-size: 0.58rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: rgba(255, 255, 255, 0.35);
}

.stat-chip-value {
  font-size: 0.95rem;
  font-weight: 800;
  font-variant-numeric: tabular-nums;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 0.55rem;
}

.action-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.55rem 0.95rem;
  border-radius: 0.7rem;
  font-size: 0.82rem;
  font-weight: 700;
  border: none;
  cursor: pointer;
  color: white;
  transition: transform 0.15s ease, box-shadow 0.15s ease;
}

.action-btn:hover {
  transform: translateY(-1px);
}

.action-btn-llc {
  background: linear-gradient(135deg, #6366f1, #7c3aed);
  box-shadow: 0 10px 25px -10px rgba(99, 102, 241, 0.6);
}

.action-btn-property {
  background: linear-gradient(135deg, #10b981, #0ea5e9);
  box-shadow: 0 10px 25px -10px rgba(16, 185, 129, 0.5);
}

.page-body {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
  padding: 1.5rem;
  max-width: 1440px;
  margin: 0 auto;
}

.landing-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.75rem;
  padding: 4rem 1.5rem;
  border-radius: 1.25rem;
  border: 1px dashed rgba(255, 255, 255, 0.12);
  background: rgba(255, 255, 255, 0.02);
  text-align: center;
  color: rgba(255, 255, 255, 0.45);
}

.landing-empty i {
  font-size: 2.2rem;
  color: rgba(255, 255, 255, 0.15);
}

.landing-empty strong {
  color: #a5b4fc;
}

.toast {
  position: fixed;
  bottom: 1.5rem;
  left: 50%;
  transform: translateX(-50%);
  background: #1e293b;
  color: white;
  border: 1px solid rgba(255, 255, 255, 0.1);
  padding: 0.65rem 1.1rem;
  border-radius: 999px;
  font-size: 0.85rem;
  z-index: 80;
  box-shadow: 0 20px 40px -15px rgba(0, 0, 0, 0.6);
}

.spin {
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.toast-enter-active,
.toast-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}

.toast-enter-from,
.toast-leave-to {
  opacity: 0;
  transform: translate(-50%, 8px);
}

@media (max-width: 860px) {
  .page-header {
    flex-direction: column;
    align-items: stretch;
  }

  .header-stats,
  .header-actions {
    justify-content: space-between;
  }
}
</style>
