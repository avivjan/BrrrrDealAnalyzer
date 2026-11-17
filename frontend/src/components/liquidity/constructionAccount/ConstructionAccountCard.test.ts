// @vitest-environment jsdom
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { linkedConstructionAccountStatus } from '../../../test/fixtures/constructionAccountStatus'

vi.mock('../../../api/constructionAccount', () => ({ constructionAccountApi: { listTransactions: vi.fn().mockResolvedValue([]), refresh: vi.fn() } }))

import ConstructionAccountCard from './ConstructionAccountCard.vue'

const sumBySource = (total_dollars: number) => ({ from_the_bank_feed_dollars: total_dollars, before_this_account_dollars: 0, entered_by_hand_dollars: 0, total_dollars })

function mountTheCard(props: Record<string, unknown> = {}, statusOverrides = {}) {
  return mount(ConstructionAccountCard, {
    props: { status: linkedConstructionAccountStatus(statusOverrides), ...props },
    global: { stubs: { RouterLink: { template: '<a><slot /></a>' }, ConstructionAccountTransactionsList: true } },
  })
}

beforeEach(() => setActivePinia(createPinia()))

describe('the compact card', () => {
  it('closed: the four numbers, each against what it is measured with, and no detail', () => {
    const card = mountTheCard({}, { loan_draws_pulled: sumBySource(35000), rehab_payments_made: sumBySource(12500) })
    expect(card.get('[data-testid="ca.deal-1.summary.balance"]').text()).toBe('$35,000')
    expect(card.get('[data-testid="ca.deal-1.summary.draws"]').text()).toBe('$35,000 of $70,000 budget')
    expect(card.get('[data-testid="ca.deal-1.summary.paid"]').text()).toBe('$12,500 of $50,000 rehab')
    expect(card.get('[data-testid="ca.deal-1.summary.end-outcome"]').text()).toBe('$25,000')
    expect(card.find('[data-testid="ca.deal-1.detail"]').exists()).toBe(false)
    expect(card.get('[data-testid="ca.deal-1.toggle"]').attributes('aria-expanded')).toBe('false')
  })

  it('a click on the summary asks to open it', async () => {
    const card = mountTheCard()
    await card.get('[data-testid="ca.deal-1.toggle"]').trigger('click')
    expect(card.emitted('toggle')).toHaveLength(1)
  })

  it('not linked: the plan in words and the Link button, outside the toggle', async () => {
    const card = mountTheCard({}, { is_linked: false })
    expect(card.get('[data-testid="ca.deal-1.summary.plan"]').text()).toContain('Under budget, you keep $20,000')
    await card.get('[data-testid="ca.deal-1.link"]').trigger('click')
    expect(card.emitted('link')).toHaveLength(1)
    expect(card.emitted('toggle')).toBeUndefined()
  })
})

describe('the open card', () => {
  it('opens on the Overview, and a tab shows its own panel', async () => {
    const card = mountTheCard({ isExpanded: true })
    expect(card.find('[data-testid="ca.deal-1.panel.overview"]').exists()).toBe(true)
    expect(card.get('[data-testid="ca.deal-1.panel.overview"]').text()).toContain('Under budget: you keep')
    expect(card.get('[data-testid="ca.deal-1.original-steal"]').text()).toBe('$20,000')
    await card.get('[data-testid="ca.deal-1.tab.money-flow"]').trigger('click')
    expect(card.find('[data-testid="ca.deal-1.panel.overview"]').exists()).toBe(false)
    expect(card.find('[data-testid="ca.deal-1.panel.money-flow"]').exists()).toBe(true)
  })

  it('a link to the transactions opens that tab', async () => {
    const card = mountTheCard({ isExpanded: true, openSection: 'transactions' })
    await flushPromises()
    expect(card.find('[data-testid="ca.deal-1.transactions-section"]').exists()).toBe(true)
  })

  it('not linked: only the Overview and the timeline', () => {
    const card = mountTheCard({ isExpanded: true }, { is_linked: false })
    expect(card.findAll('[role="tab"]').map(tab => tab.text())).toEqual(['Overview', 'Timeline & transfers'])
  })

  it('a rejected approval request says so', async () => {
    const card = mountTheCard({ isExpanded: true }, {
      transfers_made_in_the_app: [{ transfer_id: 't-1', transfer_direction: 'steal_to_primary_checking', amount_dollars: 1000, transfer_outcome: 'failed_or_cancelled_at_mercury',
        mercury_transfer_status: 'rejected', requested_at: '2026-02-01T12:00:00Z', is_in_the_bank_feed: false }],
    })
    await card.get('[data-testid="ca.deal-1.tab.timeline"]').trigger('click')
    expect(card.get('[data-testid="ca.deal-1.transfer.t-1"]').text()).toContain('Rejected in Mercury')
  })
})

describe('the rehab summary', () => {
  it('a closed-out account shows where its summary went, on the card and on the Account tab', async () => {
    const card = mountTheCard({ isExpanded: true }, {
      closed_out_at: '2026-03-01T12:00:00Z',
      latest_rehab_summary: {
        rehab_summary_id: 'summary-1', created_at: '2026-03-01T12:00:00Z', overall_delivery_state: 'delivered',
        email_delivery_status: 'delivered', email_last_error_type_name: null, emailed_at: '2026-03-01T12:00:05Z',
        drive_delivery_status: 'delivered', drive_last_error_type_name: null, saved_to_drive_at: '2026-03-01T12:00:03Z',
        drive_folder_url: 'https://drive.google.com/drive/folders/x',
      },
    })
    expect(card.get('[data-testid="ca.deal-1.summary.rehab-summary"]').text()).toContain('Summary e-mailed and saved to Drive')
    await card.get('[data-testid="ca.deal-1.tab.account"]').trigger('click')
    expect(card.get('[data-testid="ca.deal-1.rehab-summary.state"]').text()).toBe('E-mailed to you and saved to your Google Drive')
    expect(card.find('[data-testid="ca.deal-1.rehab-summary.download-pdf"]').exists()).toBe(true)
  })

  it('a live account has no summary section yet', async () => {
    const card = mountTheCard({ isExpanded: true })
    await card.get('[data-testid="ca.deal-1.tab.account"]').trigger('click')
    expect(card.find('[data-testid="ca.deal-1.rehab-summary.root"]').exists()).toBe(false)
  })
})


describe('what is left, and why the numbers (tasks/todo/ConstructionAccountCardExplanations.md)', () => {
  const chateau = {
    current_balance_dollars: 24100, available_balance_dollars: 24100, construction_budget_dollars: 73000, rehab_cost_dollars: 65000,
    loan_draws_pulled: sumBySource(52900), loan_draws_remaining_to_pull_dollars: 20100,
    rehab_payments_made: sumBySource(30750), unpaid_rehab_remaining_dollars: 34250,
    remaining_deposit_dollars: 0, projected_return_at_rehab_end_dollars: 9950, own_money_back_at_rehab_end_dollars: 5000,
    spread_at_rehab_end_dollars: 4950, safe_to_steal_now_dollars: 9950, safe_to_steal_now_is_capped_by: 'projected_return' as const,
  }

  it('shows what is left to draw and to pay, and what is safe to take out now', () => {
    const card = mountTheCard({}, chateau)
    expect(card.get('[data-testid="ca.deal-1.summary.left-to-draw"]').text()).toBe('$20,100 left to draw')
    expect(card.get('[data-testid="ca.deal-1.summary.left-to-pay"]').text()).toBe('$34,250 left to pay')
    expect(card.get('[data-testid="ca.deal-1.summary.safe-to-take-out"]').text()).toBe('$9,950')
  })

  it('the (i) of Back to you shows the calculation and does not open the card; Escape closes it', async () => {
    const card = mountTheCard({}, chateau)
    const explain = card.get('[data-testid="ca.deal-1.summary.end-outcome.explain"]')
    await explain.trigger('click')
    expect(card.emitted('toggle')).toBeUndefined()
    expect(explain.attributes('aria-expanded')).toBe('true')
    const lines = card.findAll('[data-testid="ca.deal-1.summary.end-outcome.explain.line"]').map(line => line.text().replace(/\s+/g, ' '))
    expect(lines[0]).toContain('In the account now')
    expect(lines[lines.length - 1]).toContain('Back to you at the end')
    expect(lines[lines.length - 1]).toContain('$9,950')
    await explain.trigger('keydown', { key: 'Escape' })
    expect(explain.attributes('aria-expanded')).toBe('false')
  })

  it('a click on the numbers still opens the card', async () => {
    const card = mountTheCard({}, chateau)
    await card.get('[data-testid="ca.deal-1.summary.figures"]').trigger('click')
    expect(card.emitted('toggle')).toHaveLength(1)
  })
})
