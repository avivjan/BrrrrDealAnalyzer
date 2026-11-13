/**
 * Go-to keys (tasks/todo/ConstructionAccountPerRehab.md, Step C0): `g` then a page's key opens it from anywhere —
 * `g d` Dashboard, `g m` My Deals, `g b` Bought, `g l` Liquidity, `g c` Construction accounts, and so on (each
 * page's key is `goToKey` in `shell/nav.ts`, shown as a hint in the command palette and on the `?` sheet). Never while typing in a field,
 * and never with a modifier key, so no browser or editor shortcut is taken.
 */
import { onBeforeUnmount, onMounted } from 'vue'
import type { Router } from 'vue-router'

import { NAV_ITEMS } from '../components/shell/nav'

export const GO_TO_SECOND_KEY_WAIT_MILLISECONDS = 1500

export function isTypingInAField(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false
  return target.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName)
}

/** The page the second key names, or null. Exported for the tests. */
export function goToPathOf(secondKey: string): string | null {
  return NAV_ITEMS.find(item => item.goToKey === secondKey.toLowerCase())?.to ?? null
}

/** `onAskForTheShortcutList` runs on `?` (the help sheet). */
export function useGoToKeyboardShortcuts(router: Pick<Router, 'push'>, onAskForTheShortcutList: () => void = () => {}): void {
  let waitingForTheSecondKeySince: number | null = null

  function onKeydown(event: KeyboardEvent) {
    if (event.defaultPrevented || event.metaKey || event.ctrlKey || event.altKey || isTypingInAField(event.target)) {
      waitingForTheSecondKeySince = null
      return
    }
    if (event.key === '?') {
      waitingForTheSecondKeySince = null
      event.preventDefault()
      onAskForTheShortcutList()
      return
    }
    const now = Date.now()
    if (waitingForTheSecondKeySince !== null && now - waitingForTheSecondKeySince <= GO_TO_SECOND_KEY_WAIT_MILLISECONDS) {
      waitingForTheSecondKeySince = null
      const path = goToPathOf(event.key)
      if (path) {
        event.preventDefault()
        void router.push(path)
      }
      return
    }
    waitingForTheSecondKeySince = event.key === 'g' && !event.shiftKey ? now : null
  }

  onMounted(() => window.addEventListener('keydown', onKeydown))
  onBeforeUnmount(() => window.removeEventListener('keydown', onKeydown))
}
