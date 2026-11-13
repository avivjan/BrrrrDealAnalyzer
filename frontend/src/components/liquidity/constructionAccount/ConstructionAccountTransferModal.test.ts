// @vitest-environment jsdom
import { DOMWrapper, flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { linkedConstructionAccountStatus } from '../../../test/fixtures/constructionAccountStatus'
import type { ConstructionAccountTransfer, ConstructionAccountTransferWriteResult } from '../../../types/constructionAccount'

const api = vi.hoisted(() => ({ deposit: vi.fn(), steal: vi.fn(), markClosedOut: vi.fn(), list: vi.fn() }))
vi.mock('../../../api/constructionAccount', () => ({ constructionAccountApi: api }))

import ConstructionAccountTransferModal from './ConstructionAccountTransferModal.vue'

function transfer(outcome: ConstructionAccountTransfer['transfer_outcome']): ConstructionAccountTransfer {
  return { transfer_id: 't-1', transfer_direction: 'deposit_into_construction_account', amount_dollars: 5000, transfer_outcome: outcome,
           mercury_transfer_status: 'sent', requested_at: '2026-02-01T12:00:00Z', is_in_the_bank_feed: false }
}

function answer(withTransfer: ConstructionAccountTransfer | null): ConstructionAccountTransferWriteResult {
  const status = linkedConstructionAccountStatus()
  return {
    was_preview_only: withTransfer === null, status_before: status, status_after: { ...status, remaining_deposit_dollars: 0 },
    changes_the_liquidity_timeline: true, liquidity_row_changes: null, row_descriptions_marked_done: ['Deposit into the construction account'],
    balance_left_in_the_account_dollars: null, transfer: withTransfer,
  }
}

let wrapper: VueWrapper | null = null
const at = (testid: string) => new DOMWrapper(document.querySelector(`[data-testid="${testid}"]`) as HTMLElement)
const exists = (testid: string) => document.querySelector(`[data-testid="${testid}"]`) !== null

async function openTheModal(kind: 'deposit' | 'steal' | 'close_out', statusOverrides = {}) {
  wrapper = mount(ConstructionAccountTransferModal, { props: { open: true, status: linkedConstructionAccountStatus(statusOverrides), kind } })
  await flushPromises()
}

async function typeAmount(amount: string) {
  const input = document.querySelector('[data-testid="ca-transfer.amount"]') as HTMLInputElement
  input.value = amount
  input.dispatchEvent(new Event('input'))
  await vi.advanceTimersByTimeAsync(500)
  await flushPromises()
}

beforeEach(() => {
  vi.useFakeTimers()
  setActivePinia(createPinia())
  for (const mock of Object.values(api)) mock.mockReset()
  api.list.mockResolvedValue({ totals: null, accounts: [] })
  api.deposit.mockImplementation(async (_id, _data, options) => answer(options?.previewOnly ? null : transfer('accepted_by_mercury')))
  api.steal.mockImplementation(async (_id, _data, options) => answer(options?.previewOnly ? null : transfer('accepted_by_mercury')))
})
afterEach(() => { wrapper?.unmount(); wrapper = null; vi.useRealTimers() })

describe('ConstructionAccountTransferModal', () => {
  it('opens prefilled with what is still to deposit, and previews it without asking Mercury', async () => {
    await openTheModal('deposit')
    expect((document.querySelector('[data-testid="ca-transfer.amount"]') as HTMLInputElement).value).toBe('5000')
    expect(api.deposit).toHaveBeenCalledTimes(1)
    expect(api.deposit.mock.calls[0]![2]).toMatchObject({ previewOnly: true })
    expect(at('ca-transfer.marked-done').text()).toContain('Deposit into the construction account')
    expect(at('ca-transfer.accounts').text()).toContain('AJYK checking → Oak rehab')
  })

  it('sends once with the one key of this window, then says what Mercury answered', async () => {
    await openTheModal('deposit')
    const previewKey = api.deposit.mock.calls[0]![1].idempotency_key
    await at('ca-transfer.send').trigger('click')
    await flushPromises()
    const sent = api.deposit.mock.calls.filter(call => !call[2]?.previewOnly)
    expect(sent).toHaveLength(1)
    expect(sent[0]![1]).toMatchObject({ amount_dollars: 5000, idempotency_key: previewKey })
    expect(at('ca-transfer.outcome').attributes('data-outcome')).toBe('accepted_by_mercury')
    expect(wrapper!.emitted('transferred')).toHaveLength(1)
    expect(exists('ca-transfer.send')).toBe(false)
  })

  it('a steal above safe to steal needs the top-up confirmation before it can be sent', async () => {
    await openTheModal('steal')
    await typeAmount('25000')
    expect(at('ca-transfer.top-up-warning').text()).toContain('$5,000 above safe to steal now')
    expect(at('ca-transfer.send').attributes('disabled')).toBeDefined()
    await at('ca-transfer.confirm-top-up').setValue(true)
    expect(at('ca-transfer.send').attributes('disabled')).toBeUndefined()
    await at('ca-transfer.send').trigger('click')
    await flushPromises()
    const sent = api.steal.mock.calls.filter(call => !call[2]?.previewOnly)
    expect(sent[0]![1]).toMatchObject({ amount_dollars: 25000, confirm_amount_exceeds_safe_to_steal: true })
  })

  it('a blocking problem shows and nothing can be sent or previewed', async () => {
    await openTheModal('deposit', { has_a_transfer_token: false })
    expect(at('ca-transfer.problems').text()).toContain('MERCURY_TRANSFER_API_TOKEN_AJYK')
    expect(at('ca-transfer.send').attributes('disabled')).toBeDefined()
    expect(api.deposit).not.toHaveBeenCalled()
  })

  it('no answer from Mercury says to check Mercury, and is not reported as transferred', async () => {
    api.deposit.mockImplementation(async (_id, _data, options) => answer(options?.previewOnly ? null : transfer('mercury_did_not_answer')))
    await openTheModal('deposit')
    await at('ca-transfer.send').trigger('click')
    await flushPromises()
    expect(at('ca-transfer.outcome').text()).toContain('check Mercury before trying again')
    expect(wrapper!.emitted('transferred')).toBeUndefined()
  })

  it('close out steals the whole available balance, then marks the account closed out', async () => {
    api.markClosedOut.mockResolvedValue(answer(null))
    await openTheModal('close_out', { safe_to_steal_now_dollars: 35000 })
    expect((document.querySelector('[data-testid="ca-transfer.amount"]') as HTMLInputElement).value).toBe('35000')
    await at('ca-transfer.send').trigger('click')
    await flushPromises()
    expect(api.steal.mock.calls.filter(call => !call[2]?.previewOnly)[0]![1]).toMatchObject({ amount_dollars: 35000 })
    expect(api.markClosedOut).toHaveBeenCalledWith('deal-1', expect.objectContaining({ today: expect.any(String) }))
  })

  it('a refusal from the server is shown and nothing is reported as sent', async () => {
    api.deposit.mockImplementation(async (_id, _data, options) => {
      if (options?.previewOnly) return answer(null)
      throw { response: { status: 429, data: { detail: '5 transfers in the last hour, the limit in the construction account settings. Try again later.' } } }
    })
    await openTheModal('deposit')
    await at('ca-transfer.send').trigger('click')
    await flushPromises()
    expect(at('ca-transfer.error').text()).toContain('5 transfers in the last hour')
    expect(exists('ca-transfer.outcome')).toBe(false)
  })
})
