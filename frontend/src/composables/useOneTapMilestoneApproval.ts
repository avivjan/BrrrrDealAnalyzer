/**
 * "Done" on a deal milestone (tasks/todo/LiquidityTheaterMode.md, section D, decision 2): approve it on its
 * planned date in one tap when nothing else changes. The preview is loaded quietly first; if any row would be
 * added, changed or removed, another milestone would move, or one of your own changes conflicts with the deal,
 * the usual before -> after list opens instead and nothing is applied until you confirm there.
 */
import { ref } from 'vue'

import type {
  DealCashRowChanges,
  DealMilestone,
  DealMilestoneChangeReq,
  ImportedLiquidityDeal,
  LiquidityDealBoard,
} from '../types/liquidity'
import { DEAL_MILESTONE_LABELS } from '../components/liquidity/dealMilestoneLabels'
import { dealKeyOf } from '../components/liquidity/dealColors'

export interface OneTapMilestoneApprovalDependencies {
  previewMilestoneChange: (dealBoard: LiquidityDealBoard, dealId: string, change: DealMilestoneChangeReq) => Promise<DealCashRowChanges>
  applyMilestoneChange: (dealBoard: LiquidityDealBoard, dealId: string, change: DealMilestoneChangeReq) => Promise<DealCashRowChanges>
  /** Opens the before -> after list (DealMilestoneChangeModal) for an approval. */
  openMilestoneApprovalReview: (deal: ImportedLiquidityDeal, milestone: DealMilestone) => void
  showToast: (message: string) => void
}

/** Whether approving needs a look first: any row written, any milestone moved, or a conflict with your changes. */
export function milestoneApprovalChangesSomething(preview: DealCashRowChanges): boolean {
  const counts = preview.change_counts
  return counts.added + counts.updated + counts.removed + counts.kept_no_longer_in_the_deal + counts.conflicts_with_your_changes > 0
    || preview.milestone_date_changes.length > 0
}

export function useOneTapMilestoneApproval(dependencies: OneTapMilestoneApprovalDependencies) {
  /** `${dealKey}:${milestone}` while its preview or apply runs (a spinner on its Done button). */
  const milestoneKeyBeingApproved = ref<string | null>(null)

  async function approveMilestoneOnItsPlannedDate(deal: ImportedLiquidityDeal, milestone: DealMilestone): Promise<void> {
    const plannedDate = deal.milestones.find(state => state.milestone === milestone)?.planned_date
    if (!plannedDate || milestoneKeyBeingApproved.value) return
    const approval: DealMilestoneChangeReq = { milestone, new_date: plannedDate, approve: true, use_deal_value_for: [] }
    milestoneKeyBeingApproved.value = `${dealKeyOf(deal.deal_board, deal.deal_id)}:${milestone}`
    try {
      const preview = await dependencies.previewMilestoneChange(deal.deal_board, deal.deal_id, approval)
      if (milestoneApprovalChangesSomething(preview)) {
        dependencies.openMilestoneApprovalReview(deal, milestone)
        return
      }
      await dependencies.applyMilestoneChange(deal.deal_board, deal.deal_id, approval)
      dependencies.showToast(`${DEAL_MILESTONE_LABELS[milestone]} done.`)
    } catch (error: any) {
      dependencies.showToast('Error: ' + (error?.response?.data?.detail || error?.message || 'could not approve the milestone'))
    } finally {
      milestoneKeyBeingApproved.value = null
    }
  }

  return { milestoneKeyBeingApproved, approveMilestoneOnItsPlannedDate }
}
