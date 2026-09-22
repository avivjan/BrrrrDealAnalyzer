<script setup lang="ts">
/**
 * One row of the calculation tree: sign, label, value, and, when the row is
 * itself a computed step, a chevron that opens the step's own rows (a sum) or
 * its formula (anything else) indented beneath it. Recursive: the children
 * are rows of this same component.
 *
 * Expansion state is not held here. The popup owns the set of open paths and
 * this row only reports a toggle, so "Expand all" / "Collapse all" and the
 * reset on every open are one assignment in one place.
 */
import { computed, useId } from "vue";

import type { CalcBreakdowns } from "../../types";
import { type CalculationBreakdownRow, rowsOfStep } from "./calculationBreakdownTree";
import { formatCalculationStepValueByUnit } from "./calculationStepFormat";

const props = defineProps<{
  row: CalculationBreakdownRow;
  depth: number;
  /** Labels of the steps above this row, so a step never expands into itself. */
  ancestorStepLabels: ReadonlySet<string>;
  expandedRowPaths: ReadonlySet<string>;
  breakdowns: CalcBreakdowns;
  sectionKey: string;
}>();

const emit = defineEmits<{ toggle: [path: string] }>();

const childrenId = useId();

const isExpandable = computed(() => props.row.linkedStep !== undefined);
const isExpanded = computed(() => isExpandable.value && props.expandedRowPaths.has(props.row.path));

const childAncestorStepLabels = computed<ReadonlySet<string>>(() => {
  const labels = new Set(props.ancestorStepLabels);
  if (props.row.linkedStep) labels.add(props.row.linkedStep.label);
  return labels;
});

const childRows = computed(() =>
  props.row.linkedStep
    ? rowsOfStep(props.row.linkedStep, props.breakdowns, props.sectionKey, props.row.path, childAncestorStepLabels.value)
    : [],
);

const rowValueText = computed(() => formatCalculationStepValueByUnit(props.row.unit, props.row.value));
const linkedStepValueText = computed(() =>
  props.row.linkedStep ? formatCalculationStepValueByUnit(props.row.linkedStep.unit, props.row.linkedStep.value) : "",
);

function onRowPressed() {
  if (isExpandable.value) emit("toggle", props.row.path);
}
</script>

<template>
  <li data-part="row" :data-path="row.path" :data-depth="depth" :data-expandable="isExpandable">
    <div
      class="grid grid-cols-[1.25rem_1rem_minmax(0,1fr)_auto] items-baseline gap-x-2 py-1 text-sm"
      :class="isExpandable ? 'cursor-pointer' : ''"
      @click="onRowPressed"
    >
      <button
        v-if="isExpandable"
        type="button"
        data-part="row-toggle"
        :aria-expanded="isExpanded"
        :aria-controls="childrenId"
        :aria-label="`${isExpanded ? 'Hide' : 'Show'} how ${row.label} is calculated`"
        class="flex h-5 w-5 items-center justify-center self-center rounded-ctl text-fg-muted hover:bg-surface-muted hover:text-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        @click.stop="emit('toggle', row.path)"
      >
        <i
          class="pi pi-chevron-down text-[10px] transition-transform duration-base ease-standard"
          :class="{ '-rotate-90': !isExpanded }"
          aria-hidden="true"
        ></i>
      </button>
      <span v-else class="h-5 w-5" aria-hidden="true"></span>
      <span data-part="row-sign" class="text-center font-mono text-fg-muted">{{ row.sign ?? "" }}</span>
      <span data-part="row-label" class="truncate" :class="isExpandable ? 'font-medium text-fg' : 'text-fg-muted'">
        {{ row.label }}
      </span>
      <span data-part="row-value" class="numeric tabular text-fg">{{ rowValueText }}</span>
    </div>

    <div
      v-if="isExpandable && isExpanded"
      :id="childrenId"
      data-part="row-children"
      class="mb-1 ml-[0.625rem] border-l border-line pl-3"
    >
      <ul v-if="childRows.length" class="m-0 list-none p-0">
        <CalculationBreakdownTreeRow
          v-for="childRow in childRows"
          :key="childRow.path"
          :row="childRow"
          :depth="depth + 1"
          :ancestor-step-labels="childAncestorStepLabels"
          :expanded-row-paths="expandedRowPaths"
          :breakdowns="breakdowns"
          :section-key="sectionKey"
          @toggle="emit('toggle', $event)"
        />
        <li
          data-part="row-total"
          class="grid grid-cols-[1.25rem_1rem_minmax(0,1fr)_auto] items-baseline gap-x-2 border-t border-line py-1 text-sm font-semibold"
        >
          <span aria-hidden="true"></span>
          <span class="text-center font-mono text-fg-muted">=</span>
          <span class="truncate text-fg">{{ row.linkedStep!.label }}</span>
          <span class="numeric tabular text-fg">{{ linkedStepValueText }}</span>
        </li>
      </ul>
      <p v-else data-part="row-formula" class="break-words py-1 font-mono text-xs leading-relaxed text-fg">
        {{ row.linkedStep!.formula }}
      </p>
      <p v-if="row.linkedStep!.note" data-part="row-note" class="pb-1 text-xs text-fg-muted">
        {{ row.linkedStep!.note }}
      </p>
    </div>
  </li>
</template>
