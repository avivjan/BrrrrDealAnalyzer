/**
 * One color per BRRRR deal in the liquidity timeline (tasks/todo/LiquidityTheaterMode.md, section B).
 *
 * The palette is the dataviz skill's categorical palette without its green and red slots, which this app keeps
 * for money in / money out. Six hues, validated with `validate_palette.js` in both modes (light: every adjacent
 * pair passes, three hues sit below 3:1 on white, so the deal's address is always shown next to its color; dark:
 * every check passes). A seventh deal and beyond gets the neutral color, never a generated or cycled hue.
 *
 * The slot follows the deal, never its rank: a hash of the deal's key picks a preferred slot, and a collision
 * probes for the next free one, walking the deals in key order. The same set of deals gives the same colors on
 * every device, and adding a deal keeps the others' colors unless it collides.
 */
import type { LiquidityDealBoard, LiquidityTransaction } from '../../types/liquidity'

export const DEAL_COLOR_HEX_BY_SLOT_LIGHT_MODE = ['#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#e87ba4', '#6250d6'] as const
export const DEAL_COLOR_HEX_BY_SLOT_DARK_MODE = ['#3987e5', '#d95926', '#199e70', '#c98500', '#d55181', '#9085e9'] as const
export const DEAL_COLOR_SLOT_COUNT = DEAL_COLOR_HEX_BY_SLOT_LIGHT_MODE.length
/** The color of a deal past the sixth, and of the "Other flows" entry. */
export const NEUTRAL_DEAL_COLOR_HEX = '#8a8780'

export type ColorMode = 'light' | 'dark'

export function dealKeyOf(dealBoard: LiquidityDealBoard, dealId: string): string {
  return `${dealBoard}:${dealId}`
}

/** The key of the deal a row was imported from; null for a manual row or a recurring occurrence. */
export function dealKeyOfTransaction(transaction: LiquidityTransaction): string | null {
  if (transaction.recurring_rule_id || !transaction.source_deal_board || !transaction.source_deal_id) return null
  return dealKeyOf(transaction.source_deal_board, transaction.source_deal_id)
}

/** A small, stable string hash (FNV-1a, 32 bit). */
function hashDealKey(dealKey: string): number {
  let hash = 0x811c9dc5
  for (let index = 0; index < dealKey.length; index += 1) {
    hash ^= dealKey.charCodeAt(index)
    hash = Math.imul(hash, 0x01000193) >>> 0
  }
  return hash
}

/** Each deal's color slot (0..5), or null once every slot is taken. */
export function assignDealColorSlotByDealKey(dealKeys: string[]): Map<string, number | null> {
  const colorSlotByDealKey = new Map<string, number | null>()
  const takenColorSlots = new Set<number>()
  for (const dealKey of [...new Set(dealKeys)].sort()) {
    const preferredColorSlot = hashDealKey(dealKey) % DEAL_COLOR_SLOT_COUNT
    let assignedColorSlot: number | null = null
    for (let probe = 0; probe < DEAL_COLOR_SLOT_COUNT; probe += 1) {
      const candidateColorSlot = (preferredColorSlot + probe) % DEAL_COLOR_SLOT_COUNT
      if (!takenColorSlots.has(candidateColorSlot)) {
        assignedColorSlot = candidateColorSlot
        break
      }
    }
    if (assignedColorSlot !== null) takenColorSlots.add(assignedColorSlot)
    colorSlotByDealKey.set(dealKey, assignedColorSlot)
  }
  return colorSlotByDealKey
}

export function dealColorHexForSlot(colorSlot: number | null, colorMode: ColorMode): string {
  if (colorSlot === null) return NEUTRAL_DEAL_COLOR_HEX
  const palette = colorMode === 'dark' ? DEAL_COLOR_HEX_BY_SLOT_DARK_MODE : DEAL_COLOR_HEX_BY_SLOT_LIGHT_MODE
  return palette[colorSlot] ?? NEUTRAL_DEAL_COLOR_HEX
}

/** "4431 Victor St" from "4431 Victor St, Jacksonville, FL 32207": the street line, for a compact tag. */
export function shortDealAddress(dealAddress: string): string {
  const streetLine = dealAddress.split(',')[0]?.trim()
  return streetLine || dealAddress
}
