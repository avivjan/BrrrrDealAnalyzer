<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useLiquidityStore } from '../stores/liquidityStore'
import type { LiquidityTransaction, SimulationResult } from '../types/liquidity'
import { requiresSimulation } from '../utils/liquidityEngine'
import TimelineChart from '../components/liquidity/TimelineChart.vue'
import LiquiditySidebar from '../components/liquidity/LiquiditySidebar.vue'
import DayDetail from '../components/liquidity/DayDetail.vue'
import TransactionForm from '../components/liquidity/TransactionForm.vue'
import SimulationWarning from '../components/liquidity/SimulationWarning.vue'
import SettingsPanel from '../components/liquidity/SettingsPanel.vue'

const router = useRouter()
const store = useLiquidityStore()

const chartRef = ref<InstanceType<typeof TimelineChart> | null>(null)
const selectedDate = ref<string | null>(null)
const formOpen = ref(false)
const editingTxn = ref<LiquidityTransaction | null>(null)
const prefillDate = ref<string | null>(null)
const settingsOpen = ref(false)

const warningOpen = ref(false)
const warningSeverity = ref<'hard' | 'soft' | 'none'>('none')
const warningResult = ref<SimulationResult | null>(null)
const pendingSave = ref<{ effective_date: string; description: string; amount_k: number; id?: string } | null>(null)

const toastMessage = ref('')
const toastVisible = ref(false)
let toastTimer: ReturnType<typeof setTimeout> | undefined

const selectedBucket = computed(() => {
  if (!selectedDate.value) return null
  return store.series.days.find(d => d.date === selectedDate.value) ?? null
})

const hasData = computed(() => store.transactions.length > 0 || store.settings.opening_balance_k !== 0)

onMounted(() => {
  store.fetchAll()
})

function onSelectDay(date: string) {
  selectedDate.value = date
}

function openAddForm(date?: string) {
  editingTxn.value = null
  prefillDate.value = date ?? selectedDate.value
  formOpen.value = true
}

function openEditForm(txnId: string) {
  const txn = store.transactions.find(t => t.id === txnId)
  if (txn) {
    editingTxn.value = txn
    prefillDate.value = null
    formOpen.value = true
  }
}

async function onFormSave(data: { effective_date: string; description: string; amount_k: number; id?: string }) {
  formOpen.value = false

  const needsSim = data.id
    ? requiresSimulation(store.transactions.find(t => t.id === data.id)!, data.amount_k, data.effective_date)
    : requiresSimulation(null, data.amount_k, data.effective_date)

  if (needsSim) {
    const fakeTxn: LiquidityTransaction = {
      id: data.id || '__candidate__',
      effective_date: data.effective_date,
      description: data.description,
      amount_k: data.amount_k,
    }
    const action = data.id ? 'edit' : 'add'
    const candidateList = store.buildCandidateList(action, fakeTxn, data.id)
    const result = store.runSimulation(candidateList)

    if (result.negativeDates.length > 0) {
      warningSeverity.value = 'hard'
      warningResult.value = result
      pendingSave.value = data
      warningOpen.value = true
      return
    }

    if (result.breachesReserve) {
      warningSeverity.value = 'soft'
      warningResult.value = result
      pendingSave.value = data
      warningOpen.value = true
      return
    }

    // Comfortable — save and show toast
    await doSave(data)
    showToast(`Saved. Window min: ${result.min.toFixed(1)}k on ${result.minDates[0]}`)
    return
  }

  await doSave(data)
  showToast('Transaction saved.')
}

async function onWarningConfirm() {
  warningOpen.value = false
  if (pendingSave.value) {
    await doSave(pendingSave.value)
    pendingSave.value = null
  }
}

function onWarningCancel() {
  warningOpen.value = false
  pendingSave.value = null
}

async function doSave(data: { effective_date: string; description: string; amount_k: number; id?: string }) {
  try {
    if (data.id) {
      await store.updateTransaction(data.id, {
        effective_date: data.effective_date,
        description: data.description,
        amount_k: data.amount_k,
      })
    } else {
      await store.addTransaction({
        effective_date: data.effective_date,
        description: data.description,
        amount_k: data.amount_k,
      })
    }
  } catch (e: any) {
    showToast('Error: ' + (e?.response?.data?.detail || e.message))
  }
}

async function onDeleteTxn(txnId: string) {
  try {
    await store.deleteTransaction(txnId)
    showToast('Transaction deleted.')
  } catch (e: any) {
    showToast('Error: ' + (e?.response?.data?.detail || e.message))
  }
}

async function onSettingsSave(data: { opening_balance_k: number; opening_balance_date: string; reserve_k: number }) {
  settingsOpen.value = false
  try {
    await store.updateSettings(data)
    showToast('Settings saved.')
  } catch (e: any) {
    showToast('Error: ' + (e?.response?.data?.detail || e.message))
  }
}

function showToast(msg: string) {
  toastMessage.value = msg
  toastVisible.value = true
  if (toastTimer) clearTimeout(toastTimer)
  toastTimer = setTimeout(() => { toastVisible.value = false }, 4000)
}
</script>

<template>
  <div class="min-h-screen bg-[#0f1117] text-slate-200 flex flex-col">
    <!-- Header -->
    <header class="flex items-center justify-between px-4 py-3 border-b border-[#1e2030] bg-[#0f1117]/90 backdrop-blur-sm sticky top-0 z-30">
      <div class="flex items-center gap-3">
        <button
          class="w-8 h-8 flex items-center justify-center rounded-lg text-slate-400 hover:text-slate-200 hover:bg-[#1e2030] transition-all"
          title="Back"
          @click="router.push('/')"
        >
          <i class="pi pi-arrow-left text-sm"></i>
        </button>
        <h1 class="text-base font-mono font-bold text-slate-100 tracking-tight">
          <i class="pi pi-chart-line text-indigo-400 mr-2"></i>
          Liquidity Timeline
        </h1>
      </div>
      <div class="flex items-center gap-2">
        <button
          class="px-3 py-1.5 text-xs font-mono text-slate-400 hover:text-slate-200 hover:bg-[#1e2030] rounded-lg transition-all flex items-center gap-1.5"
          @click="chartRef?.centerOnToday()"
        >
          <i class="pi pi-crosshair text-[10px]"></i> Today
        </button>
        <button
          class="px-3 py-1.5 text-xs font-mono text-slate-400 hover:text-slate-200 hover:bg-[#1e2030] rounded-lg transition-all flex items-center gap-1.5"
          @click="settingsOpen = true"
        >
          <i class="pi pi-cog text-[10px]"></i> Settings
        </button>
        <button
          class="px-3 py-1.5 text-xs font-mono font-semibold bg-indigo-500/20 text-indigo-300 hover:bg-indigo-500/30 border border-indigo-500/30 rounded-lg transition-all flex items-center gap-1.5"
          @click="openAddForm()"
        >
          <i class="pi pi-plus text-[10px]"></i> Add Flow
        </button>
      </div>
    </header>

    <!-- Loading -->
    <div v-if="store.loading" class="flex-1 flex items-center justify-center">
      <div class="text-center">
        <i class="pi pi-spin pi-spinner text-2xl text-indigo-400 mb-3"></i>
        <p class="text-sm font-mono text-slate-500">Loading liquidity data...</p>
      </div>
    </div>

    <!-- Error -->
    <div v-else-if="store.error" class="flex-1 flex items-center justify-center">
      <div class="text-center max-w-sm">
        <i class="pi pi-exclamation-circle text-3xl text-red-400 mb-3"></i>
        <p class="text-sm font-mono text-red-300 mb-2">Failed to load</p>
        <p class="text-xs font-mono text-slate-500 mb-4">{{ store.error }}</p>
        <button
          class="px-4 py-2 text-xs font-mono bg-[#1e2030] border border-[#2a2f45] rounded-lg text-slate-300 hover:border-indigo-500 transition-all"
          @click="store.fetchAll()"
        >
          Retry
        </button>
      </div>
    </div>

    <!-- Empty state -->
    <div v-else-if="!hasData && !store.loading" class="flex-1 flex items-center justify-center">
      <div class="text-center max-w-md">
        <div class="w-16 h-16 mx-auto mb-4 rounded-2xl bg-indigo-500/10 flex items-center justify-center">
          <i class="pi pi-chart-line text-3xl text-indigo-400"></i>
        </div>
        <h2 class="text-lg font-mono font-bold text-slate-200 mb-2">No liquidity data yet</h2>
        <p class="text-sm font-mono text-slate-500 mb-6">
          Set your opening balance and add your first cash flow to get started.
        </p>
        <div class="flex gap-3 justify-center">
          <button
            class="px-4 py-2 text-sm font-mono bg-[#1e2030] border border-[#2a2f45] rounded-lg text-slate-300 hover:border-indigo-500 transition-all"
            @click="settingsOpen = true"
          >
            Set Opening Balance
          </button>
          <button
            class="px-4 py-2 text-sm font-mono font-semibold bg-indigo-500/20 text-indigo-300 hover:bg-indigo-500/30 border border-indigo-500/30 rounded-lg transition-all"
            @click="openAddForm()"
          >
            Add First Flow
          </button>
        </div>
      </div>
    </div>

    <!-- Main content -->
    <div v-else class="flex-1 flex min-h-0">
      <!-- Chart area -->
      <div class="flex-1 flex flex-col min-w-0">
        <div class="flex-1 min-h-[300px]">
          <TimelineChart
            ref="chartRef"
            :days="store.series.days"
            :global-min="store.series.globalMin"
            :global-min-dates="store.series.globalMinDates"
            :first-negative-date="store.series.firstNegativeDate"
            @select-day="onSelectDay"
          />
        </div>

        <!-- Bottom detail panel -->
        <div class="border-t border-[#1e2030] p-3 bg-[#0f1117] max-h-[260px] overflow-y-auto">
          <DayDetail
            v-if="selectedBucket"
            :bucket="selectedBucket"
            @edit-txn="openEditForm"
            @delete-txn="onDeleteTxn"
            @add-on-date="openAddForm"
          />
          <div v-else class="text-xs font-mono text-slate-500 py-4 text-center">
            Click or arrow-key to a day to see details
          </div>
        </div>
      </div>

      <!-- Right sidebar -->
      <aside class="w-56 border-l border-[#1e2030] p-3 overflow-y-auto hidden lg:block bg-[#0f1117]">
        <LiquiditySidebar
          :series="store.series"
          :settings="store.settings"
          :transactions="store.transactions"
        />
      </aside>
    </div>

    <!-- Modals -->
    <TransactionForm
      :open="formOpen"
      :edit-txn="editingTxn"
      :prefill-date="prefillDate"
      @close="formOpen = false"
      @save="onFormSave"
    />

    <SimulationWarning
      :open="warningOpen"
      :result="warningResult"
      :severity="warningSeverity"
      @confirm="onWarningConfirm"
      @cancel="onWarningCancel"
    />

    <SettingsPanel
      :open="settingsOpen"
      :settings="store.settings"
      @close="settingsOpen = false"
      @save="onSettingsSave"
    />

    <!-- Toast -->
    <Transition name="toast">
      <div
        v-if="toastVisible"
        class="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 bg-[#1e2030] border border-[#2a2f45] rounded-lg px-4 py-2.5 shadow-xl text-xs font-mono text-slate-300 max-w-md"
      >
        {{ toastMessage }}
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.toast-enter-active, .toast-leave-active {
  transition: all 0.3s ease;
}
.toast-enter-from {
  opacity: 0;
  transform: translate(-50%, 12px);
}
.toast-leave-to {
  opacity: 0;
  transform: translate(-50%, 12px);
}
</style>
