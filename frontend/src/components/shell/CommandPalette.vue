<script setup lang="ts">
/**
 * `Cmd/Ctrl+K`. A combobox over a listbox inside a modal dialog: type to
 * filter, arrows to move, Enter to run, Escape to close. Focus goes to the
 * input on open and back to where it was on close. Running a command closes
 * the palette first, so a navigation never races the leave animation.
 */
import { computed, nextTick, onBeforeUnmount, ref, useId, watch } from "vue";
import { useRouter } from "vue-router";

import { inertOutside } from "../ui/inertOutside";
import { setLook, setTheme, toggleTheme } from "../../design/theme";
import { apiClient } from "../../api";
import type { ImportedLiquidityDeal } from "../../types/liquidity";
import { buildCommands, buildDealCommands, filterCommands, type Command, type PaletteDeal } from "./commands";

const props = defineProps<{ open: boolean }>();
const emit = defineEmits<{ close: []; openSettings: [] }>();

const router = useRouter();
const commands = buildCommands({
  router,
  setTheme,
  setLook,
  toggleTheme,
  openSettings: () => emit("openSettings"),
});

/**
 * Every deal, read once when the palette first opens (the compact cross-board list, and which deals are in the
 * liquidity timeline), so "Open <address>" works from anywhere. A failed read leaves only the page commands.
 */
const dealCommands = ref<Command[]>([]);
let dealsWereRead = false;
async function readDealsOnce(): Promise<void> {
  if (dealsWereRead) return;
  dealsWereRead = true;
  const [dealList, importedDeals] = await Promise.allSettled([
    apiClient.get<PaletteDeal[]>("/deals", { params: { limit: 500 } }),
    apiClient.get<ImportedLiquidityDeal[]>("/liquidity/deals"),
  ]);
  if (dealList.status !== "fulfilled") {
    dealsWereRead = false;
    return;
  }
  const inTheTimeline = new Set(importedDeals.status === "fulfilled" ? importedDeals.value.data.map((deal) => `${deal.deal_board}:${deal.deal_id}`) : []);
  dealCommands.value = buildDealCommands(dealList.value.data, router, (board, dealId) => inTheTimeline.has(`${board}:${dealId}`));
}

const query = ref("");
const activeIndex = ref(0);
const input = ref<HTMLInputElement | null>(null);
const listId = useId();
let restoreTo: HTMLElement | null = null;
let releaseInert: (() => void) | null = null;

// The deals are many: they show once something is typed.
const results = computed(() => filterCommands(query.value.trim() ? [...commands, ...dealCommands.value] : commands, query.value));
const active = computed<Command | undefined>(() => results.value[activeIndex.value]);

/** Groups in first-seen order, for the headings between rows. */
const grouped = computed(() => {
  const order: Command["group"][] = [];
  const byGroup = new Map<Command["group"], Command[]>();
  for (const command of results.value) {
    if (!byGroup.has(command.group)) {
      byGroup.set(command.group, []);
      order.push(command.group);
    }
    byGroup.get(command.group)!.push(command);
  }
  return order.map((group) => ({ group, items: byGroup.get(group)! }));
});

watch(results, () => {
  activeIndex.value = 0;
});

watch(
  () => props.open,
  async (open) => {
    if (typeof document === "undefined") return;
    if (open) {
      void readDealsOnce();
      restoreTo = document.activeElement instanceof HTMLElement ? document.activeElement : null;
      query.value = "";
      activeIndex.value = 0;
      await nextTick();
      input.value?.focus();
      const root = input.value?.closest<HTMLElement>('[data-testid="shell.command"]') ?? null;
      releaseInert?.();
      releaseInert = root ? inertOutside(root) : null;
    } else {
      releaseInert?.();
      releaseInert = null;
      if (restoreTo) {
        restoreTo.focus();
        restoreTo = null;
      }
    }
  },
  // `immediate`: a palette mounted already open (a test, a deep link) focuses too.
  { immediate: true },
);

onBeforeUnmount(() => {
  releaseInert?.();
  releaseInert = null;
});

function run(command: Command) {
  emit("close");
  command.run();
}

function onKeydown(event: KeyboardEvent) {
  switch (event.key) {
    case "Escape":
      // Claim the key: a drawer open underneath listens on document and defers
      // to a prevented Escape.
      event.preventDefault();
      event.stopPropagation();
      emit("close");
      break;
    case "ArrowDown":
      event.preventDefault();
      if (results.value.length) activeIndex.value = (activeIndex.value + 1) % results.value.length;
      break;
    case "ArrowUp":
      event.preventDefault();
      if (results.value.length) activeIndex.value = (activeIndex.value - 1 + results.value.length) % results.value.length;
      break;
    case "Enter":
      event.preventDefault();
      if (active.value) run(active.value);
      break;
    default:
  }
}
</script>

<template>
  <Teleport to="body">
    <UiTransition preset="commandPalette">
      <div
        v-if="open"
        data-testid="shell.command"
        data-overlay
        class="fixed inset-0 z-50 flex items-start justify-center bg-fg/40 px-3 pt-[max(3rem,12vh)]"
        @click.self="emit('close')"
        @keydown="onKeydown"
      >
        <div
          role="dialog"
          aria-modal="true"
          aria-label="Command palette"
          data-ui="modal-panel"
          class="flex w-full max-w-xl flex-col overflow-hidden rounded-panel border-ui border-line bg-surface text-fg shadow-4"
        >
          <div class="flex items-center gap-3 border-b border-line px-4">
            <i class="pi pi-search text-sm text-fg-muted" aria-hidden="true" />
            <input
              ref="input"
              v-model="query"
              data-testid="shell.command.input"
              type="text"
              role="combobox"
              aria-label="Search commands"
              aria-autocomplete="list"
              :aria-expanded="results.length > 0"
              :aria-controls="listId"
              :aria-activedescendant="active ? `cmd-${active.id}` : undefined"
              autocomplete="off"
              spellcheck="false"
              placeholder="Jump to a page, change the look…"
              class="min-h-12 flex-1 bg-transparent text-base text-fg outline-none placeholder:text-fg-muted"
            />
            <kbd class="numeric hidden rounded-[4px] border-ui border-line bg-surface-2 px-1.5 py-0.5 text-[10px] text-fg-muted sm:inline">Esc</kbd>
          </div>

          <div :id="listId" role="listbox" aria-label="Commands" class="custom-scrollbar max-h-[min(24rem,60vh)] overflow-y-auto p-2">
            <template v-for="section in grouped" :key="section.group">
              <div class="px-3 pb-1 pt-2 text-[11px] font-semibold uppercase tracking-[0.1em] text-fg-muted" aria-hidden="true">
                {{ section.group }}
              </div>
              <UiCommandItem
                v-for="command in section.items"
                :key="command.id"
                :id="command.id"
                :label="command.label"
                :hint="command.hint"
                :icon="command.icon"
                :active="active?.id === command.id"
                :data-testid="`shell.command.item.${command.id}`"
                @click="run(command)"
                @mousemove="activeIndex = results.indexOf(command)"
              />
            </template>
            <p v-if="results.length === 0" class="px-3 py-6 text-center text-sm text-fg-muted">No matching command.</p>
          </div>
        </div>
      </div>
    </UiTransition>
  </Teleport>
</template>
