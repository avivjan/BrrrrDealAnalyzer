/**
 * Each deal in progress on the liquidity timeline, from its contract to its refi, as one thin line per deal at the bottom
 * of the chart (tasks/todo/ConstructionAccountPerRehab.md, Step G). One lane per deal, so lines never overlap. A deal
 * whose refi is approved is over and has no line; a refi already late runs through today.
 */
import type { ImportedLiquidityDeal } from '../types/liquidity'
import { dealKeyOf } from '../components/liquidity/dealColors'

export interface DealLifespan {
  dealKey: string
  startDate: string
  endDate: string
  refiIsLate: boolean
  /** 0 = the lowest lane. */
  laneIndex: number
}

export function dealLifespansOf(importedDeals: readonly ImportedLiquidityDeal[], todayIsoDate: string): DealLifespan[] {
  const lifespans: Omit<DealLifespan, 'laneIndex'>[] = []
  for (const deal of importedDeals) {
    const contract = deal.milestones.find(milestone => milestone.milestone === 'contract_signed')
    const refi = deal.milestones.find(milestone => milestone.milestone === 'refi_closed')
    if (!contract || !refi || refi.approved_at) continue
    const startDate = contract.approved_at ? contract.approved_at.slice(0, 10) : contract.planned_date
    const refiIsLate = refi.planned_date < todayIsoDate
    lifespans.push({ dealKey: dealKeyOf(deal.deal_board, deal.deal_id), startDate, endDate: refiIsLate ? todayIsoDate : refi.planned_date, refiIsLate })
  }
  return lifespans
    .sort((first, second) => first.startDate.localeCompare(second.startDate) || first.dealKey.localeCompare(second.dealKey))
    .map((lifespan, laneIndex) => ({ ...lifespan, laneIndex }))
}
