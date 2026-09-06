<script setup lang="ts">
/**
 * A presentational data table: sticky header, aligned columns, sortable
 * headers that *announce* a sort and let the caller perform it.
 *
 * The table never reorders `rows`. Clicking a sortable header emits
 * `update:sort` with the next `{ key, dir }`; the parent decides what that
 * means for its data and passes the rows back in whatever order it likes. That
 * keeps sorting a piece of presentational view state, not behaviour hidden in
 * a primitive. `rowClick` is emitted for every row so a parent can open a
 * detail; the row becomes keyboard-reachable only when the parent listens.
 *
 * Cells render `row[column.key]` unless a `cell-<key>` slot takes over; the
 * `empty` slot fills the body when there are no rows.
 */
import { computed, getCurrentInstance, useAttrs } from "vue";

import { cn } from "../../design/cn";

export interface DataTableColumn {
  key: string;
  label: string;
  align?: "left" | "right" | "center";
  width?: string;
  sortable?: boolean;
  /** Render the cell in the mono numeric face. */
  numeric?: boolean;
}

export interface DataTableSort {
  key: string;
  dir: "asc" | "desc";
}

type Row = Record<string, unknown>;

const props = withDefaults(
  defineProps<{
    columns: DataTableColumn[];
    rows: Row[];
    /** The property that identifies a row. */
    rowKey: string;
    sort?: DataTableSort | null;
    dense?: boolean;
    /** A caption for assistive tech; visually hidden. */
    caption?: string;
  }>(),
  { sort: null, dense: false, caption: undefined },
);

const emit = defineEmits<{
  "update:sort": [sort: DataTableSort];
  rowClick: [row: Row];
}>();

defineOptions({ inheritAttrs: false });

const attrs = useAttrs();

function passthrough() {
  const rest: Record<string, unknown> = { ...attrs };
  delete rest.class;
  return rest;
}

// `rowClick` is a declared emit, so Vue strips its listener out of `attrs`;
// the vnode still carries it, and that is the only way to know a parent cares.
const instance = getCurrentInstance();
const clickable = computed(() => typeof instance?.vnode.props?.onRowClick === "function");

const ALIGN: Record<NonNullable<DataTableColumn["align"]>, string> = {
  left: "text-left",
  right: "text-right",
  center: "text-center",
};

function headerClick(column: DataTableColumn) {
  if (!column.sortable) return;
  const dir = props.sort?.key === column.key && props.sort.dir === "asc" ? "desc" : "asc";
  emit("update:sort", { key: column.key, dir });
}

function ariaSort(column: DataTableColumn): "ascending" | "descending" | "none" | undefined {
  if (!column.sortable) return undefined;
  if (props.sort?.key !== column.key) return "none";
  return props.sort.dir === "asc" ? "ascending" : "descending";
}

const cellPad = computed(() => (props.dense ? "px-3 py-1.5" : "px-4 py-2.5"));

const rootClass = computed(() =>
  cn("w-full overflow-x-auto rounded-card border-ui border-line bg-surface", attrs.class as string),
);
</script>

<template>
  <div data-ui="data-table" :class="rootClass" v-bind="passthrough()">
    <table class="w-full border-collapse text-sm">
      <caption v-if="caption" class="sr-only">{{ caption }}</caption>
      <thead class="sticky top-0 z-[1] bg-surface-2 text-[11px] uppercase tracking-[0.08em] text-fg-muted">
        <tr>
          <th
            v-for="column in columns"
            :key="column.key"
            scope="col"
            :aria-sort="ariaSort(column)"
            :style="column.width ? { width: column.width } : undefined"
            :class="cn('border-b border-line font-semibold', cellPad, ALIGN[column.align ?? 'left'])"
          >
            <button
              v-if="column.sortable"
              type="button"
              data-part="sort"
              :class="
                cn(
                  'inline-flex min-h-8 items-center gap-1 rounded-ctl uppercase tracking-[0.08em]',
                  'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                  sort?.key === column.key ? 'text-fg' : 'text-fg-muted',
                )
              "
              @click="headerClick(column)"
            >
              <slot :name="`header-${column.key}`" :column="column">{{ column.label }}</slot>
              <i
                aria-hidden="true"
                :class="
                  cn(
                    'pi text-[10px]',
                    sort?.key === column.key
                      ? sort.dir === 'asc'
                        ? 'pi-arrow-up'
                        : 'pi-arrow-down'
                      : 'pi-sort-alt opacity-50',
                  )
                "
              />
            </button>
            <slot v-else :name="`header-${column.key}`" :column="column">{{ column.label }}</slot>
          </th>
        </tr>
      </thead>
      <tbody>
        <tr v-if="rows.length === 0">
          <td :colspan="columns.length" data-part="empty" :class="cn('text-center text-fg-muted', cellPad)">
            <slot name="empty">—</slot>
          </td>
        </tr>
        <tr
          v-for="row in rows"
          v-else
          :key="String(row[rowKey])"
          data-part="row"
          :tabindex="clickable ? 0 : undefined"
          :class="
            cn(
              'border-b border-line last:border-b-0 transition-colors duration-fast',
              clickable && 'cursor-pointer hover:bg-surface-2 focus-visible:bg-surface-2 focus-visible:outline-none',
            )
          "
          @click="emit('rowClick', row)"
          @keydown.enter="emit('rowClick', row)"
        >
          <td
            v-for="column in columns"
            :key="column.key"
            :class="cn(cellPad, ALIGN[column.align ?? 'left'], column.numeric && 'numeric')"
          >
            <slot :name="`cell-${column.key}`" :row="row" :value="row[column.key]">{{ row[column.key] }}</slot>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
