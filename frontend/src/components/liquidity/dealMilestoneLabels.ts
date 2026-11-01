import type { DealMilestone } from '../../types/liquidity'

export const DEAL_MILESTONE_LABELS: Record<DealMilestone, string> = {
  contract_signed: 'Contract signed',
  purchase_closed: 'Purchase closed',
  rehab_completed: 'Rehab completed',
  tenant_moved_in: 'Tenant moved in',
  refi_closed: 'Refi closed',
}
