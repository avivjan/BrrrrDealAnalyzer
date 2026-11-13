/**
 * "This changes the liquidity timeline" (tasks/todo/ConstructionAccountPerRehab.md, Requirement 1): every change that
 * moves a deal's liquidity rows asks first, at the point of the change, and nothing changes until Confirm.
 *
 * One prompt is open at a time, per deal. Requests queue behind it, except that a change for the deal whose prompt is
 * already open is merged into it (its preview is read again), so a second prompt never opens on top. A change the
 * bank reported was already applied: it opens an OK-only version of the same list.
 *
 * After a Confirm, one "Liquidity timeline updated" notice shows; more confirms while it is visible update it in place
 * ("3 edits · 5 rows") instead of stacking notices.
 */
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import type { DealCashRowChanges, UseDealValueForField } from '../types/liquidity'

/** A figure the change moves, shown above the rows: "Rehab cost $50,000 → $58,000". */
export interface LiquidityTimelineFigureChange {
  label: string
  before: string
  after: string
}

export interface LiquidityTimelineChangePreview {
  rowChanges: DealCashRowChanges | null
  figureChanges: LiquidityTimelineFigureChange[]
  rowDescriptionsMarkedDone: string[]
}

export interface LiquidityTimelineChangeRequest {
  /** One prompt per deal: "bought:<id>" or "my_deals:<id>". */
  dealKey: string
  title: string
  /** Read what the change would do (nothing is saved). Called again when something else changes for the same deal. */
  loadPreview: (useTheNewValueFor: UseDealValueForField[]) => Promise<LiquidityTimelineChangePreview>
  /** Save the change. Answers how many timeline rows it changed. */
  confirm: (useTheNewValueFor: UseDealValueForField[]) => Promise<number>
}

/** What already happened, shown with OK only. */
export interface LiquidityTimelineBankReport {
  dealKey: string
  title: string
  preview: LiquidityTimelineChangePreview
}

interface OpenPrompt {
  request: LiquidityTimelineChangeRequest | null
  bankReport: LiquidityTimelineBankReport | null
  preview: LiquidityTimelineChangePreview | null
  useTheNewValueFor: UseDealValueForField[]
  isLoading: boolean
  isConfirming: boolean
  errorMessage: string | null
  settle: ((confirmed: boolean) => void)[]
}

interface QueuedPrompt {
  request: LiquidityTimelineChangeRequest | null
  bankReport: LiquidityTimelineBankReport | null
  settle: ((confirmed: boolean) => void)[]
}

export const NOTICE_VISIBLE_MILLISECONDS = 6000

export function changedRowCountOf(preview: LiquidityTimelineChangePreview): number {
  const counts = preview.rowChanges?.change_counts
  return (counts ? counts.added + counts.updated + counts.removed : 0) + preview.rowDescriptionsMarkedDone.length
}

function errorMessageOf(error: unknown): string {
  const detail = (error as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
  return typeof detail === 'string' ? detail : 'That did not work. Nothing was changed.'
}

export const useLiquidityTimelineChangePromptStore = defineStore('liquidityTimelineChangePrompt', () => {
  const open = ref<OpenPrompt | null>(null)
  const queue = ref<QueuedPrompt[]>([])

  const notice = ref<{ editCount: number; rowCount: number; message: string } | null>(null)
  let noticeTimer: ReturnType<typeof setTimeout> | null = null

  const isOpen = computed(() => open.value !== null)
  const isABankReport = computed(() => open.value?.bankReport != null)

  async function loadOpenPreview(): Promise<void> {
    const current = open.value
    if (!current?.request) return
    current.isLoading = true
    current.errorMessage = null
    try {
      const preview = await current.request.loadPreview(current.useTheNewValueFor)
      if (open.value === current) current.preview = preview
    } catch (error) {
      if (open.value === current) current.errorMessage = errorMessageOf(error)
    } finally {
      if (open.value === current) current.isLoading = false
    }
  }

  function openNext(): void {
    const next = queue.value.shift()
    if (!next) {
      open.value = null
      return
    }
    open.value = {
      request: next.request, bankReport: next.bankReport, preview: next.bankReport?.preview ?? null,
      useTheNewValueFor: [], isLoading: false, isConfirming: false, errorMessage: null, settle: next.settle,
    }
    void loadOpenPreview()
  }

  function close(confirmed: boolean): void {
    const settled = open.value?.settle ?? []
    open.value = null
    for (const settle of settled) settle(confirmed)
    openNext()
  }

  /** Ask before a change. Resolves true once it is confirmed and saved, false when cancelled. */
  function ask(request: LiquidityTimelineChangeRequest): Promise<boolean> {
    return new Promise((resolve) => {
      if (open.value?.request && open.value.request.dealKey === request.dealKey) {
        // The same deal: the newer change replaces the open one, and the list is read again (merged, never stacked).
        open.value.request = request
        open.value.settle.push(resolve)
        void loadOpenPreview()
        return
      }
      const queued = queue.value.find(entry => entry.request?.dealKey === request.dealKey)
      if (queued) {
        queued.request = request
        queued.settle.push(resolve)
        return
      }
      queue.value.push({ request, bankReport: null, settle: [resolve] })
      if (!open.value) openNext()
    })
  }

  /** The bank reported a change that was already applied. Merged into an open prompt of the same deal. */
  function reportFromTheBank(bankReport: LiquidityTimelineBankReport): void {
    if (open.value?.request && open.value.request.dealKey === bankReport.dealKey) {
      void loadOpenPreview()
      return
    }
    if (open.value?.bankReport?.dealKey === bankReport.dealKey) {
      open.value.preview = bankReport.preview
      return
    }
    if (queue.value.some(entry => entry.request?.dealKey === bankReport.dealKey)) return   // its prompt will read it
    queue.value.push({ request: null, bankReport, settle: [] })
    if (!open.value) openNext()
  }

  function setUseTheNewValueFor(choices: UseDealValueForField[]): void {
    if (!open.value) return
    open.value.useTheNewValueFor = choices
    void loadOpenPreview()
  }

  function showTimelineUpdated(rowCount: number): void {
    if (noticeTimer) clearTimeout(noticeTimer)
    const editCount = (notice.value?.editCount ?? 0) + 1
    const totalRowCount = (notice.value?.rowCount ?? 0) + rowCount
    notice.value = {
      editCount, rowCount: totalRowCount,
      message: editCount === 1
        ? `Liquidity timeline updated: ${totalRowCount} ${totalRowCount === 1 ? 'row' : 'rows'}`
        : `Liquidity timeline updated: ${editCount} edits · ${totalRowCount} ${totalRowCount === 1 ? 'row' : 'rows'}`,
    }
    noticeTimer = setTimeout(dismissNotice, NOTICE_VISIBLE_MILLISECONDS)
  }

  /** An edit that moved no timeline row: a short notice, not a prompt. */
  function showSaved(message = 'Saved'): void {
    if (noticeTimer) clearTimeout(noticeTimer)
    notice.value = { editCount: 0, rowCount: 0, message }
    noticeTimer = setTimeout(dismissNotice, NOTICE_VISIBLE_MILLISECONDS)
  }

  function dismissNotice(): void {
    if (noticeTimer) clearTimeout(noticeTimer)
    noticeTimer = null
    notice.value = null
  }

  async function confirm(): Promise<void> {
    const current = open.value
    if (!current) return
    if (!current.request) {   // a bank report: OK
      close(true)
      return
    }
    current.isConfirming = true
    current.errorMessage = null
    try {
      const rowCount = await current.request.confirm(current.useTheNewValueFor)
      showTimelineUpdated(rowCount)
      close(true)
    } catch (error) {
      current.errorMessage = errorMessageOf(error)
      current.isConfirming = false
    }
  }

  function cancel(): void {
    if (open.value) close(false)
  }

  return {
    open, queue, isOpen, isABankReport, notice,
    ask, reportFromTheBank, setUseTheNewValueFor, confirm, cancel, showTimelineUpdated, showSaved, dismissNotice,
  }
})
