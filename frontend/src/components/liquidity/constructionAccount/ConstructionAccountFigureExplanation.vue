<script setup lang="ts">
/**
 * An (i) beside a figure that explains it (tasks/todo/ConstructionAccountCardExplanations.md): a plain sentence and the
 * calculation, line by line. It opens while a mouse is over it or the keyboard reached it, and a click or tap keeps it
 * open (phones); a second tap, Escape or a tap outside closes it. Clicks inside never reach the card, so explaining a figure never opens the card.
 */
import { computed, onBeforeUnmount, ref, useId } from 'vue'

import type { FigureExplanation } from '../../../utils/constructionAccountFigureExplanations'
import { formatMoney } from '../../../utils/money'

const props = withDefaults(defineProps<{
  explanation: FigureExplanation
  figureName: string
  testid: string
  /** Tailwind classes that place the panel (it opens below the (i)); default: aligned to its right edge. */
  panelPositionClass?: string
}>(), { panelPositionClass: 'right-0' })

const panelId = useId()
const isOpenedByClick = ref(false)
/** A mouse over it (never a finger: a tap is a click). */
const isHoveredByAMouse = ref(false)
/** Reached with the keyboard (Tab), not by a click. */
const isFocusedFromTheKeyboard = ref(false)
const isPanelVisible = computed(() => isOpenedByClick.value || isHoveredByAMouse.value || isFocusedFromTheKeyboard.value)
const rootElement = ref<HTMLElement | null>(null)

function onPointerEnter(event: PointerEvent) {
  if (event.pointerType === 'mouse') isHoveredByAMouse.value = true
}

function onFocus(event: FocusEvent) {
  isFocusedFromTheKeyboard.value = (event.target as HTMLElement).matches?.(':focus-visible') ?? false
}

function closeEverything() {
  setOpenedByClick(false)
  isHoveredByAMouse.value = false
  isFocusedFromTheKeyboard.value = false
}

const OPERATION_SIGNS = { start: '', plus: '+', minus: '−', result: '=' } as const

function closeOnOutsidePointer(event: Event) {
  if (!(event.target instanceof Node) || !rootElement.value?.contains(event.target)) setOpenedByClick(false)
}

function setOpenedByClick(isOpen: boolean) {
  isOpenedByClick.value = isOpen
  if (isOpen) document.addEventListener('pointerdown', closeOnOutsidePointer, { capture: true })
  else document.removeEventListener('pointerdown', closeOnOutsidePointer, { capture: true })
}

onBeforeUnmount(() => document.removeEventListener('pointerdown', closeOnOutsidePointer, { capture: true }))
</script>

<template>
  <span ref="rootElement" class="relative inline-flex" :data-open="isPanelVisible" @click.stop @keydown.escape.stop="closeEverything"
        @pointerenter="onPointerEnter" @pointerleave="isHoveredByAMouse = false">
    <button type="button" :data-testid="testid" :aria-label="`How ${props.figureName} is calculated`" :aria-expanded="isPanelVisible"
            :aria-describedby="panelId" @click="setOpenedByClick(!isOpenedByClick)" @focus="onFocus" @blur="isFocusedFromTheKeyboard = false"
            class="inline-flex h-5 w-5 items-center justify-center rounded-full text-fg-muted hover:bg-surface-muted hover:text-fg focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary">
      <i class="pi pi-info-circle text-[11px]" aria-hidden="true"></i>
    </button>
    <span :id="panelId" role="tooltip" :data-testid="`${testid}.panel`"
          class="absolute top-full z-40 mt-2 w-[19rem] max-w-[calc(100vw-2rem)] rounded-ctl border-ui border-line bg-surface-3 p-3 text-left text-xs text-fg shadow-3 transition-opacity duration-fast ease-standard"
          :class="[panelPositionClass, isPanelVisible ? 'visible opacity-100' : 'invisible opacity-0 pointer-events-none']">
      <span class="block font-normal leading-snug text-fg-muted">{{ explanation.summary }}</span>
      <span class="mt-2 block space-y-1 border-t border-line pt-2">
        <span v-for="(line, lineIndex) in explanation.lines" :key="lineIndex" :data-testid="`${testid}.line`"
              class="flex items-start justify-between gap-3" :class="line.operation === 'result' ? 'border-t border-line pt-1 font-semibold' : ''">
          <span class="flex min-w-0 gap-1">
            <span class="numeric w-3 shrink-0 text-fg-muted">{{ OPERATION_SIGNS[line.operation] }}</span>
            <span class="min-w-0">
              {{ line.label }}
              <span v-if="line.detail" class="block text-[11px] font-normal text-fg-muted">{{ line.detail }}</span>
            </span>
          </span>
          <span class="numeric shrink-0">{{ formatMoney(line.amountDollars) }}</span>
        </span>
      </span>
      <span v-if="explanation.footnote" class="mt-2 block leading-snug text-fg-muted">{{ explanation.footnote }}</span>
    </span>
  </span>
</template>
