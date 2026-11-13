// @vitest-environment jsdom
import { mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, h } from 'vue'

import { CONSTRUCTION_ACCOUNTS_PATH } from '../navigation/appLinks'
import { GO_TO_SECOND_KEY_WAIT_MILLISECONDS, goToPathOf, isTypingInAField, useGoToKeyboardShortcuts } from './useGoToKeyboardShortcuts'

function mountWithShortcuts() {
  const router = { push: vi.fn() }
  const openTheShortcutList = vi.fn()
  const Shell = defineComponent({ setup() { useGoToKeyboardShortcuts(router, openTheShortcutList); return () => h('div') } })
  const wrapper = mount(Shell, { attachTo: document.body })
  return { router, openTheShortcutList, wrapper }
}

function press(key: string, target: EventTarget = window, extra: KeyboardEventInit = {}) {
  target.dispatchEvent(new KeyboardEvent('keydown', { key, bubbles: true, cancelable: true, ...extra }))
}

let cleanUp: (() => void) | null = null
afterEach(() => { cleanUp?.(); cleanUp = null; vi.useRealTimers() })

describe('go-to keys', () => {
  it('maps each second key to its page', () => {
    expect(goToPathOf('l')).toBe('/liquidity')
    expect(goToPathOf('c')).toBe(CONSTRUCTION_ACCOUNTS_PATH)
    expect(goToPathOf('B')).toBe('/bought-deals')
    expect(goToPathOf('z')).toBeNull()
  })

  it('g then c opens the Construction Accounts page', () => {
    const { router, wrapper } = mountWithShortcuts()
    cleanUp = () => wrapper.unmount()
    press('g'); press('c')
    expect(router.push).toHaveBeenCalledWith(CONSTRUCTION_ACCOUNTS_PATH)
  })

  it('is ignored while typing in a field', () => {
    const { router, wrapper } = mountWithShortcuts()
    const field = document.createElement('input')
    document.body.appendChild(field)
    cleanUp = () => { wrapper.unmount(); field.remove() }
    expect(isTypingInAField(field)).toBe(true)
    press('g', field); press('l', field)
    expect(router.push).not.toHaveBeenCalled()
  })

  it('is ignored with a modifier key, and after the wait for the second key', () => {
    vi.useFakeTimers()
    const { router, wrapper } = mountWithShortcuts()
    cleanUp = () => wrapper.unmount()
    press('g', window, { ctrlKey: true }); press('l')
    press('g'); vi.advanceTimersByTime(GO_TO_SECOND_KEY_WAIT_MILLISECONDS + 1); press('l')
    expect(router.push).not.toHaveBeenCalled()
  })

  it('? opens the shortcut list, except while typing', () => {
    const { openTheShortcutList, wrapper } = mountWithShortcuts()
    const field = document.createElement('textarea')
    document.body.appendChild(field)
    cleanUp = () => { wrapper.unmount(); field.remove() }
    press('?', field, { shiftKey: true })
    expect(openTheShortcutList).not.toHaveBeenCalled()
    press('?', window, { shiftKey: true })
    expect(openTheShortcutList).toHaveBeenCalledTimes(1)
  })
})
