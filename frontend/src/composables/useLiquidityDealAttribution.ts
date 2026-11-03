/**
 * Which deal a liquidity row belongs to, and that deal's color (tasks/todo/LiquidityTheaterMode.md, section B).
 *
 * The liquidity view provides the lookup once; any row component injects it. A component mounted without it (a
 * contract test, another page) gets null and simply shows no deal tag.
 *
 * Every imported deal is in the lookup, including a deal whose rows are all done: its done rows keep their address
 * and color even though the legend no longer lists it.
 */
import { computed, inject, provide, type ComputedRef, type InjectionKey, type Ref } from 'vue'

import {
  assignDealColorSlotByDealKey,
  dealColorHexForSlot,
  dealKeyOf,
  dealKeyOfTransaction,
  shortDealAddress,
  type ColorMode,
} from '../components/liquidity/dealColors'
import { resolvedTheme } from '../design/theme'
import type { ImportedLiquidityDeal, LiquidityDealBoard, LiquidityTransaction } from '../types/liquidity'

export interface DealAttribution {
  dealKey: string
  dealBoard: LiquidityDealBoard
  dealId: string
  dealAddress: string
  shortDealAddress: string
  dealColorHex: string
}

export interface DealAttributionLookup {
  attributionForTransaction: (transaction: LiquidityTransaction) => DealAttribution | null
  attributionForDealKey: (dealKey: string) => DealAttribution | null
}

export const DEAL_ATTRIBUTION_LOOKUP_INJECTION_KEY: InjectionKey<ComputedRef<DealAttributionLookup>> = Symbol('dealAttributionLookup')

export function buildDealAttributionLookup(importedDeals: ImportedLiquidityDeal[], colorMode: ColorMode): DealAttributionLookup {
  const dealKeys = importedDeals.map(deal => dealKeyOf(deal.deal_board, deal.deal_id))
  const colorSlotByDealKey = assignDealColorSlotByDealKey(dealKeys)
  const attributionByDealKey = new Map<string, DealAttribution>()
  for (const deal of importedDeals) {
    const dealKey = dealKeyOf(deal.deal_board, deal.deal_id)
    attributionByDealKey.set(dealKey, {
      dealKey,
      dealBoard: deal.deal_board,
      dealId: deal.deal_id,
      dealAddress: deal.deal_address,
      shortDealAddress: shortDealAddress(deal.deal_address),
      dealColorHex: dealColorHexForSlot(colorSlotByDealKey.get(dealKey) ?? null, colorMode),
    })
  }
  const attributionForDealKey = (dealKey: string) => attributionByDealKey.get(dealKey) ?? null
  return {
    attributionForDealKey,
    attributionForTransaction: (transaction) => {
      const dealKey = dealKeyOfTransaction(transaction)
      return dealKey ? attributionForDealKey(dealKey) : null
    },
  }
}

/** Called once by the liquidity view: every row component below it can show its deal. */
export function provideLiquidityDealAttribution(importedDeals: Ref<ImportedLiquidityDeal[]>): ComputedRef<DealAttributionLookup> {
  const dealAttributionLookup = computed(() => buildDealAttributionLookup(importedDeals.value, resolvedTheme.value))
  provide(DEAL_ATTRIBUTION_LOOKUP_INJECTION_KEY, dealAttributionLookup)
  return dealAttributionLookup
}

/** The provided lookup, or null when nothing provides one. */
export function useInjectedDealAttributionLookup(): ComputedRef<DealAttributionLookup> | null {
  return inject(DEAL_ATTRIBUTION_LOOKUP_INJECTION_KEY, null)
}

/**
 * A row's left accent in its deal's color (an inset shadow, so the row's box does not change); none for a manual
 * row. Takes the lookup itself: a template unwraps the injected ref.
 */
export function dealAccentStyleForTransaction(
  dealAttributionLookup: DealAttributionLookup | null,
  transaction: LiquidityTransaction,
): Record<string, string> {
  const dealAttribution = dealAttributionLookup?.attributionForTransaction(transaction) ?? null
  return dealAttribution ? { boxShadow: `inset 3px 0 0 ${dealAttribution.dealColorHex}` } : {}
}
