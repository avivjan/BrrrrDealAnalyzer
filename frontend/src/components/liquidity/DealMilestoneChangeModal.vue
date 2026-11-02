<script setup lang="ts">
/**
 * Approve or move one milestone of an imported deal. The date is picked first; the list of every affected row
 * (moved, amount changed, added, removed, kept) and every milestone that moves with it is shown before anything
 * changes. "Confirm" writes the date to the deal and re-syncs its rows (decisions 8, 9 and 14).
 */
import { computed, onMounted, ref, watch } from 'vue'

import { useLiquidityStore } from '../../stores/liquidityStore'
import type { DealCashRowChanges, DealMilestone, ImportedLiquidityDeal, UseDealValueForField } from '../../types/liquidity'
import UiButton from '../ui/UiButton.vue'
import UiModalPanel from '../ui/UiModalPanel.vue'
import DealCashRowChangesList from './DealCashRowChangesList.vue'
import { DEAL_MILESTONE_LABELS } from './dealMilestoneLabels'

const props = defineProps<{
  deal: ImportedLiquidityDeal
  milestone: DealMilestone
  /** True = "it happened" (approve); false = move the planned date. */
  approve: boolean
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'applied', result: DealCashRowChanges): void
}>()

const liquidityStore = useLiquidityStore()
const plannedDate = computed(() => props.deal.milestones.find(state => state.milestone === props.milestone)?.planned_date ?? '')
const newDate = ref(plannedDate.value)
const useDealValueFor = ref<UseDealValueForField[]>([])
const preview = ref<DealCashRowChanges | null>(null)
const loadingPreview = ref(false)
const applying = ref(false)
const errorMessage = ref<string | null>(null)

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
function shortDate(isoDate: string): string {
  const [year, month, day] = isoDate.split('-')
  return `${MONTHS[Number(month) - 1] ?? ''} ${Number(day)}, ${year}`
}

function changeRequest() {
  return { milestone: props.milestone, new_date: newDate.value, approve: props.approve, use_deal_value_for: useDealValueFor.value }
}

async function loadPreview() {
  if (!newDate.value) return
  loadingPreview.value = true
  errorMessage.value = null
  try {
    preview.value = await liquidityStore.previewMilestoneChange(props.deal.deal_board, props.deal.deal_id, changeRequest())
  } catch (error: any) {
    preview.value = null
    errorMessage.value = error?.response?.data?.detail || error?.message || 'Could not preview this change'
  } finally {
    loadingPreview.value = false
  }
}
onMounted(loadPreview)
watch(newDate, () => {
  useDealValueFor.value = []
  void loadPreview()
})

function onUseDealValueForChanged(choices: UseDealValueForField[]) {
  useDealValueFor.value = choices
  void loadPreview()
}

const rowCountThatChanges = computed(() => {
  const counts = preview.value?.change_counts
  return counts ? counts.added + counts.updated + counts.removed + counts.kept_no_longer_in_the_deal : 0
})

async function confirmChange() {
  applying.value = true
  errorMessage.value = null
  try {
    const result = await liquidityStore.applyMilestoneChange(props.deal.deal_board, props.deal.deal_id, changeRequest())
    emit('applied', result)
    emit('close')
  } catch (error: any) {
    errorMessage.value = error?.response?.data?.detail || error?.message || 'The change failed'
  } finally {
    applying.value = false
  }
}
</script>

<template>
  <Teleport to="body">
    <div data-testid="deal-milestone-change" class="fixed inset-0 z-50 flex items-center justify-center p-4" @keydown.esc="emit('close')">
      <div class="absolute inset-0 bg-fg/50 md:backdrop-blur-sm" @click="emit('close')" />
      <UiModalPanel size="lg" labelled-by="deal-milestone-change-title" class="relative">
        <template #header>
          <h2 id="deal-milestone-change-title" class="font-display text-lg font-semibold tracking-display text-fg">
            {{ approve ? 'Approve' : 'Move' }}: {{ DEAL_MILESTONE_LABELS[milestone] }}
          </h2>
          <p class="text-sm text-fg-muted">{{ deal.deal_address }} · planned {{ shortDate(plannedDate) }}</p>
        </template>

        <label class="flex flex-col gap-1 text-sm">
          <span class="text-fg-muted">{{ approve ? 'It happened on' : 'New planned date' }}</span>
          <input v-model="newDate" data-testid="deal-milestone-change.date" type="date" class="rounded-ctl border-ui border-line bg-surface px-2 py-1 text-fg" />
        </label>

        <p v-if="errorMessage" data-testid="deal-milestone-change.error" class="mt-2 text-sm text-negative">{{ errorMessage }}</p>
        <p v-if="loadingPreview && !preview" class="mt-2 text-sm text-fg-muted">Loading the affected rows…</p>

        <template v-if="preview">
          <ul v-if="preview.milestone_date_changes.length" data-testid="deal-milestone-change.milestones" class="mt-3 text-sm">
            <li v-for="moved in preview.milestone_date_changes" :key="moved.milestone" class="text-fg">
              {{ DEAL_MILESTONE_LABELS[moved.milestone] }}: {{ shortDate(moved.date_before) }} → <strong>{{ shortDate(moved.date_after) }}</strong>
            </li>
          </ul>
          <h3 class="mt-3 text-sm font-semibold text-fg">{{ rowCountThatChanges }} liquidity row{{ rowCountThatChanges === 1 ? '' : 's' }} change</h3>
          <DealCashRowChangesList
            class="mt-2"
            :changes="preview.changes"
            :use-deal-value-for="useDealValueFor"
            @update:use-deal-value-for="onUseDealValueForChanged"
          />
        </template>

        <template #footer>
          <div class="flex justify-end gap-2">
            <UiButton variant="ghost" @click="emit('close')">Cancel</UiButton>
            <UiButton data-testid="deal-milestone-change.confirm" :loading="applying" :disabled="!preview || applying" @click="confirmChange">Confirm</UiButton>
          </div>
        </template>
      </UiModalPanel>
    </div>
  </Teleport>
</template>
