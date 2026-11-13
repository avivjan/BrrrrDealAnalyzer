import { describe, expect, it } from 'vitest'
import { createMemoryHistory, createRouter, type LocationQuery, type RouteLocationRaw } from 'vue-router'

import {
  constructionAccountOfDeal, constructionAccountSettings, dealOnItsBoard, dealOnTheLiquidityTimeline, liquiditySettings,
  readConstructionAccountLinkQuery, readDealLinkQuery, readLiquidityLinkQuery, transactionOnTheLiquidityTimeline,
} from './appLinks'

/** The query a link puts in the address bar, as the page that opens reads it back. */
function queryOf(link: RouteLocationRaw): LocationQuery {
  const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/:anything(.*)*', component: {} }] })
  return router.resolve(link).query
}

describe('appLinks: every link reads back as what it points at', () => {
  it('a deal on its board opens that deal on My Deals or Bought', () => {
    expect(dealOnItsBoard('my_deals', 'deal-1')).toMatchObject({ path: '/my-deals' })
    expect(dealOnItsBoard('bought', 'deal-2', 'FLIP')).toMatchObject({ path: '/bought-deals' })
    expect(readDealLinkQuery(queryOf(dealOnItsBoard('bought', 'deal-2', 'FLIP')))).toEqual({ dealId: 'deal-2', dealType: 'FLIP' })
    expect(readDealLinkQuery(queryOf(dealOnItsBoard('my_deals', 'deal-1')))).toEqual({ dealId: 'deal-1', dealType: 'BRRRR' })
  })

  it('a deal on the timeline names its board and id', () => {
    const link = readLiquidityLinkQuery(queryOf(dealOnTheLiquidityTimeline('bought', 'deal-3')))
    expect(link).toEqual({ deal: { board: 'bought', dealId: 'deal-3' }, transactionId: null, day: null, openSettings: false })
  })

  it('a transaction on the timeline names the row and its day', () => {
    const link = readLiquidityLinkQuery(queryOf(transactionOnTheLiquidityTimeline('txn-9', '2026-12-01')))
    expect(link).toEqual({ deal: null, transactionId: 'txn-9', day: '2026-12-01', openSettings: false })
  })

  it('the liquidity settings link opens the settings', () => {
    expect(readLiquidityLinkQuery(queryOf(liquiditySettings()))?.openSettings).toBe(true)
  })

  it('a construction account link scrolls to the deal and can open a section', () => {
    expect(readConstructionAccountLinkQuery(queryOf(constructionAccountOfDeal('deal-4')))).toEqual({ boughtDealId: 'deal-4', section: null })
    expect(readConstructionAccountLinkQuery(queryOf(constructionAccountOfDeal('deal-4', 'transactions'))))
      .toEqual({ boughtDealId: 'deal-4', section: 'transactions' })
    expect(readConstructionAccountLinkQuery(queryOf(constructionAccountSettings()))).toEqual({ boughtDealId: null, section: 'settings' })
  })
})

describe('appLinks: a query that is not a link is read as nothing', () => {
  it('an empty query opens nothing on any page', () => {
    expect(readDealLinkQuery({})).toBeNull()
    expect(readLiquidityLinkQuery({})).toBeNull()
    expect(readConstructionAccountLinkQuery({})).toBeNull()
  })

  it('an unknown board, a malformed day, an unknown section and an overlong id are ignored', () => {
    expect(readLiquidityLinkQuery({ deal: 'somewhere:deal-1' })).toBeNull()
    expect(readLiquidityLinkQuery({ deal: 'bought:' })).toBeNull()
    expect(readLiquidityLinkQuery({ day: 'tomorrow' })).toBeNull()
    expect(readConstructionAccountLinkQuery({ open: 'everything' })).toBeNull()
    expect(readDealLinkQuery({ openDeal: 'x'.repeat(201) })).toBeNull()
  })

  it('a repeated query value uses its first value', () => {
    expect(readDealLinkQuery({ openDeal: ['deal-1', 'deal-2'] })?.dealId).toBe('deal-1')
  })
})
