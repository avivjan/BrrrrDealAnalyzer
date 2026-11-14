<script setup lang="ts">
/**
 * A construction account in two short rows (tasks/todo/ConstructionAccountsCompactCardsAndRehabSummary.md): the
 * property, its state and the one thing to do now; then the four numbers that matter, each with what it is measured
 * against. Clicking it opens the full detail under it.
 */
import { computed } from 'vue'

import type { ConstructionAccountStatus } from '../../../types/constructionAccount'
import { constructionAccountStateOf } from '../../../utils/constructionAccountState'
import { constructionAccountSummaryFiguresOf } from '../../../utils/constructionAccountSummaryFigures'
import { formatMoney } from '../../../utils/money'

const props = defineProps<{
  status: ConstructionAccountStatus
  isExpanded: boolean
  detailElementId: string
}>()

const emit = defineEmits<{
  (e: 'toggle'): void
  (e: 'link'): void
}>()

const hook = (name: string) => `ca.${props.status.bought_deal_id}.${name}`
const stateChip = computed(() => constructionAccountStateOf(props.status))
const summaryFigures = computed(() => constructionAccountSummaryFiguresOf(props.status))
const closedOutOn = computed(() => props.status.closed_out_at
  ? new Date(props.status.closed_out_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' }) : null)
</script>

<template>
  <div class="flex flex-wrap items-stretch gap-3 sm:flex-nowrap">
    <button
      type="button"
      :data-testid="hook('toggle')"
      :aria-expanded="isExpanded"
      :aria-controls="detailElementId"
      class="min-w-0 flex-1 rounded-ctl text-left focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary"
      @click="emit('toggle')"
    >
      <!-- Row 1: the property, its state, what to do now -->
      <span class="flex flex-wrap items-center gap-2">
        <i class="pi text-xs text-fg-muted transition-transform" :class="isExpanded ? 'pi-chevron-down' : 'pi-chevron-right'" aria-hidden="true"></i>
        <span :data-testid="hook('address')" class="min-w-0 truncate font-display text-base font-semibold tracking-display text-fg sm:text-lg">{{ status.deal_address }}</span>
        <!-- The state, unless the urgent action already says it with its amount -->
        <UiBadge :data-testid="hook('state')" :tone="stateChip.tone" :class="summaryFigures.urgentAction ? 'sr-only' : ''">{{ stateChip.label }}</UiBadge>
        <UiBadge v-if="summaryFigures.urgentAction" :data-testid="hook('summary.urgent-action')" :tone="summaryFigures.urgentAction.tone">
          <i class="pi pi-exclamation-triangle mr-1 text-[10px]" aria-hidden="true"></i>{{ summaryFigures.urgentAction.label }}
        </UiBadge>
        <span v-if="closedOutOn" class="text-xs text-fg-muted">Closed out {{ closedOutOn }}</span>
        <span v-if="status.latest_rehab_summary" :data-testid="hook('summary.rehab-summary')" class="text-xs"
              :class="status.latest_rehab_summary.overall_delivery_state === 'delivered' ? 'text-positive' : 'text-warning'">
          {{ status.latest_rehab_summary.overall_delivery_state === 'delivered' ? '· Summary e-mailed and saved to Drive' : '· Summary not delivered yet' }}
        </span>
      </span>

      <!-- Row 2, linked: the four numbers that matter -->
      <span v-if="status.is_linked" class="mt-3 grid grid-cols-2 gap-x-4 gap-y-3 lg:grid-cols-4">
        <span class="flex flex-col">
          <span class="text-xs text-fg-muted">In the account now</span>
          <span :data-testid="hook('summary.balance')" class="numeric text-base font-bold text-fg">{{ formatMoney(summaryFigures.moneyInTheAccountDollars) || '—' }}</span>
        </span>
        <span class="flex flex-col">
          <span class="text-xs text-fg-muted">Lender draws received</span>
          <span :data-testid="hook('summary.draws')" class="numeric text-sm text-fg">
            <span class="font-bold">{{ formatMoney(summaryFigures.lenderDrawsReceivedOutOfLenderBudget.amountDollars) }}</span>
            <span class="text-fg-muted"> of {{ formatMoney(summaryFigures.lenderDrawsReceivedOutOfLenderBudget.totalDollars) }} budget</span>
          </span>
          <span class="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-surface-muted" aria-hidden="true">
            <span class="block h-full rounded-full bg-primary" :style="{ width: `${summaryFigures.lenderDrawsReceivedOutOfLenderBudget.percentOfTotal}%` }"></span>
          </span>
        </span>
        <span class="flex flex-col">
          <span class="text-xs text-fg-muted">Paid to contractors</span>
          <span :data-testid="hook('summary.paid')" class="numeric text-sm text-fg">
            <span class="font-bold">{{ formatMoney(summaryFigures.paidToContractorsOutOfRehabCost.amountDollars) }}</span>
            <span class="text-fg-muted"> of {{ formatMoney(summaryFigures.paidToContractorsOutOfRehabCost.totalDollars) }} rehab</span>
          </span>
          <span class="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-surface-muted" aria-hidden="true">
            <span class="block h-full rounded-full bg-positive" :style="{ width: `${summaryFigures.paidToContractorsOutOfRehabCost.percentOfTotal}%` }"></span>
          </span>
        </span>
        <span class="flex flex-col">
          <template v-if="summaryFigures.rehabEndOutcome.kind === 'you_need_to_add_now'">
            <span class="text-xs text-fg-muted">You need to add now</span>
            <span :data-testid="hook('summary.end-outcome')" class="numeric text-base font-bold text-negative">{{ formatMoney(summaryFigures.rehabEndOutcome.dollars) }}</span>
          </template>
          <template v-else>
            <span class="text-xs text-fg-muted">{{ status.closed_out_at ? 'Came back to you' : 'Back to you at the end' }}</span>
            <span :data-testid="hook('summary.end-outcome')" class="numeric text-base font-bold text-positive">{{ formatMoney(summaryFigures.rehabEndOutcome.dollars) }}</span>
          </template>
        </span>
      </span>

      <!-- Row 2, not linked yet: the plan from the deal -->
      <span v-else :data-testid="hook('summary.plan')" class="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-sm">
        <span><span class="text-fg-muted">Rehab cost</span> <span class="numeric font-semibold text-fg">{{ formatMoney(status.rehab_cost_dollars) }}</span></span>
        <span><span class="text-fg-muted">Lender budget</span> <span class="numeric font-semibold text-fg">{{ formatMoney(status.construction_budget_dollars) }}</span></span>
        <span v-if="summaryFigures.rehabBudgetDifference.kind === 'under_budget_you_keep'">
          <span class="text-fg-muted">Under budget, you keep</span> <span class="numeric font-semibold text-positive">{{ formatMoney(summaryFigures.rehabBudgetDifference.dollars) }}</span>
        </span>
        <span v-else>
          <span class="text-fg-muted">Over budget, you cover</span> <span class="numeric font-semibold text-warning">{{ formatMoney(summaryFigures.rehabBudgetDifference.dollars) }}</span>
        </span>
        <span><span class="text-fg-muted">You deposit</span> <span class="numeric font-semibold text-fg">{{ formatMoney(status.total_to_deposit_dollars) }}</span></span>
      </span>
    </button>

    <div v-if="!status.is_linked" class="flex items-center">
      <UiButton size="sm" :data-testid="hook('link')" @click="emit('link')">
        <i class="pi pi-link mr-1.5 text-xs" aria-hidden="true"></i>Link an account
      </UiButton>
    </div>
  </div>
</template>
