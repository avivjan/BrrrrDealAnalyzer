<script setup lang="ts">
/**
 * An auto-calculated dollar figure shown beside the inputs that feed it — "Cash to Close
 * (Buy) $16,386". Renders nothing while `value` is null (an input it needs is missing),
 * which is the rule for every derived figure on the form.
 *
 * With `editable` it grows a small pencil: the figure stays a result, but clicking the
 * pencil swaps the amount for a compact box so a known real-world figure (the seller tax
 * credit on a settlement statement) can be typed and the parent can back-solve the input
 * behind it. Deliberately a step less easy than an input: nothing is written until Enter
 * or blur, and Escape or an empty box abandons the edit.
 */
import { computed, nextTick, ref } from "vue";
import { formatMoney, parseMoney, toEditableText } from "../../utils/money";

const props = withDefaults(
  defineProps<{
    label: string;
    value: number | null | undefined;
    /** Colour the figure by its sign (a negative wire, a positive credit). */
    signed?: boolean;
    /** A short aside under the label ("22 days through Jan 31"). */
    hint?: string;
    /** Show the pencil that lets the figure be typed over (the parent decides what that means). */
    editable?: boolean;
    /** The pencil's accessible name; "Edit <label>" when not given. */
    editAriaLabel?: string;
  }>(),
  { signed: false, hint: undefined, editable: false, editAriaLabel: undefined },
);

const emit = defineEmits<{ commitEditedValue: [dollars: number] }>();

const valueToneClass = computed(() => {
  if (!props.signed || props.value == null || props.value === 0) return "text-fg";
  return props.value > 0 ? "text-positive" : "text-negative";
});

const isEditing = ref(false);
const editDraft = ref("");
const editInput = ref<HTMLInputElement | null>(null);

const startEditing = async () => {
  editDraft.value = toEditableText(props.value);
  isEditing.value = true;
  await nextTick();
  editInput.value?.focus();
  editInput.value?.select();
};

const cancelEditing = () => {
  isEditing.value = false;
};

/** Parse the draft as plain dollars (no `k` shorthand) and hand it to the parent; an empty or unreadable box is a cancel. */
const commitEditing = () => {
  if (!isEditing.value) return;
  isEditing.value = false;
  const { dollars } = parseMoney(editDraft.value, false);
  if (dollars == null) return;
  emit("commitEditedValue", dollars);
};

const onEditKeydown = (event: KeyboardEvent) => {
  if (event.key === "Enter") {
    commitEditing();
  } else if (event.key === "Escape") {
    // Blur would commit, so leave edit mode first: the draft is dropped, nothing is emitted.
    cancelEditing();
  }
};
</script>

<template>
  <div
    v-if="value != null"
    data-ui="auto-figure"
    :data-editing="editable ? isEditing : undefined"
    class="flex items-baseline justify-between gap-3 rounded-ctl bg-surface-3/60 px-3 py-2"
  >
    <span class="min-w-0">
      <span data-part="label" class="block text-xs font-medium text-fg-muted">{{ label }}</span>
      <span v-if="hint" data-part="hint" class="block text-[11px] text-fg-muted">{{ hint }}</span>
    </span>
    <span class="inline-flex shrink-0 items-center gap-1">
      <input
        v-if="editable && isEditing"
        ref="editInput"
        data-part="edit-input"
        type="text"
        inputmode="decimal"
        autocomplete="off"
        class="ui-input numeric h-7 w-28 px-2 text-sm"
        :aria-label="editAriaLabel ?? `Edit ${label}`"
        :value="editDraft"
        @input="editDraft = ($event.target as HTMLInputElement).value"
        @keydown="onEditKeydown"
        @blur="commitEditing"
      />
      <span v-else data-part="value" class="numeric text-sm font-semibold" :class="valueToneClass">{{ formatMoney(value) }}</span>
      <UiIconButton
        v-if="editable && !isEditing"
        data-part="edit"
        size="sm"
        class="-my-1 h-6 w-6"
        :label="editAriaLabel ?? `Edit ${label}`"
        :title="editAriaLabel ?? `Edit ${label}`"
        @click="startEditing"
      >
        <i class="pi pi-pencil text-[11px]" aria-hidden="true"></i>
      </UiIconButton>
    </span>
  </div>
</template>
