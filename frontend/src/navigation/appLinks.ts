/**
 * Every link between pages, in one place (tasks/todo/ConstructionAccountPerRehab.md, Step C0): wherever a deal, a row
 * or an account is shown, one click reaches the same thing everywhere else. Each page reads back exactly the query
 * these build (`readDealLinkQuery` and friends below), so a link can never drift from what its page understands.
 */
import type { LocationQuery, RouteLocationRaw } from 'vue-router'

import type { LiquidityDealBoard } from '../types/liquidity'

export type DealTypeOnABoard = 'BRRRR' | 'FLIP'
export type ConstructionAccountSection = 'transactions' | 'manual-entries' | 'settings' | 'link'
const CONSTRUCTION_ACCOUNT_SECTIONS: readonly ConstructionAccountSection[] = ['transactions', 'manual-entries', 'settings', 'link']

export const CONSTRUCTION_ACCOUNTS_PATH = '/liquidity/construction-accounts'
export const MERCURY_WEB_APP_URL = 'https://app.mercury.com/'

/** The deal's modal on its board: My Deals or Bought. */
export function dealOnItsBoard(board: LiquidityDealBoard, dealId: string, dealType: DealTypeOnABoard = 'BRRRR'): RouteLocationRaw {
  return board === 'bought'
    ? { path: '/bought-deals', query: { openDeal: dealId, dealType } }
    : { path: '/my-deals', query: { openDeal: dealId, dealType } }
}

/** The liquidity timeline with the deal's legend entry open and its rows highlighted on the chart. */
export function dealOnTheLiquidityTimeline(board: LiquidityDealBoard, dealId: string): RouteLocationRaw {
  return { path: '/liquidity', query: { deal: `${board}:${dealId}` } }
}

/** The liquidity timeline centred on a day, with that day open and one row highlighted. */
export function transactionOnTheLiquidityTimeline(transactionId: string, isoDate: string): RouteLocationRaw {
  return { path: '/liquidity', query: { transaction: transactionId, day: isoDate } }
}

/** The Construction Accounts page scrolled to one deal's card, optionally with a section open. */
export function constructionAccountOfDeal(boughtDealId: string, section?: ConstructionAccountSection): RouteLocationRaw {
  return { path: CONSTRUCTION_ACCOUNTS_PATH, query: section ? { deal: boughtDealId, open: section } : { deal: boughtDealId } }
}

/** The Construction Accounts page with its settings drawer open. */
export function constructionAccountSettings(): RouteLocationRaw {
  return { path: CONSTRUCTION_ACCOUNTS_PATH, query: { open: 'settings' } }
}

/** The liquidity timeline with its settings open. */
export function liquiditySettings(): RouteLocationRaw {
  return { path: '/liquidity', query: { open: 'settings' } }
}

export function inspectionSummary(inspectionId: string): RouteLocationRaw {
  return { name: 'inspection-summary', params: { inspectionId } }
}

// --- What each page reads back ---------------------------------------------------------------------------------

function single(value: LocationQuery[string] | undefined): string | null {
  const first = Array.isArray(value) ? value[0] : value
  return typeof first === 'string' && first.length > 0 && first.length <= 200 ? first : null
}

export interface DealLinkQuery {
  dealId: string
  dealType: DealTypeOnABoard
}

/** `?openDeal=…&dealType=…` (My Deals, Bought). */
export function readDealLinkQuery(query: LocationQuery): DealLinkQuery | null {
  const dealId = single(query.openDeal)
  if (!dealId) return null
  return { dealId, dealType: single(query.dealType) === 'FLIP' ? 'FLIP' : 'BRRRR' }
}

export interface LiquidityLinkQuery {
  deal: { board: LiquidityDealBoard; dealId: string } | null
  transactionId: string | null
  day: string | null
  openSettings: boolean
}

/** `?deal=<board>:<id>`, `?transaction=…&day=…`, `?open=settings` (Liquidity). */
export function readLiquidityLinkQuery(query: LocationQuery): LiquidityLinkQuery | null {
  const dealValue = single(query.deal)
  const separator = dealValue?.indexOf(':') ?? -1
  const board = dealValue && separator > 0 ? dealValue.slice(0, separator) : null
  const deal = board === 'bought' || board === 'my_deals' ? { board, dealId: dealValue!.slice(separator + 1) } as const : null
  const day = single(query.day)
  const result: LiquidityLinkQuery = {
    deal: deal && deal.dealId ? deal : null,
    transactionId: single(query.transaction),
    day: day && /^\d{4}-\d{2}-\d{2}$/.test(day) ? day : null,
    openSettings: single(query.open) === 'settings',
  }
  return result.deal || result.transactionId || result.day || result.openSettings ? result : null
}

export interface ConstructionAccountLinkQuery {
  boughtDealId: string | null
  section: ConstructionAccountSection | null
}

/** `?deal=<bought deal id>&open=<section>` (Construction Accounts). */
export function readConstructionAccountLinkQuery(query: LocationQuery): ConstructionAccountLinkQuery | null {
  const boughtDealId = single(query.deal)
  const section = single(query.open)
  const knownSection = CONSTRUCTION_ACCOUNT_SECTIONS.includes(section as ConstructionAccountSection) ? section as ConstructionAccountSection : null
  return boughtDealId || knownSection ? { boughtDealId, section: knownSection } : null
}
