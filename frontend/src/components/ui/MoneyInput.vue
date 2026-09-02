<script setup lang="ts">
/**
 * A money field that shows real dollars.
 *
 * Two things make this a plain `<input type="text">` rather than PrimeVue's
 * `InputNumber`:
 *
 * 1. `InputNumber` cannot express the `k` / `m` shorthand (see `utils/money`).
 * 2. Its live currency mask re-formats on every keystroke and drags the caret
 *    to the end, which is what made the old fields so unpleasant to edit.
 *
 * So: while focused the input holds plain digits the user fully controls, and
 * the formatted `$50,500` is rendered only once they leave. The value commits
 * on blur / Enter — the same commit point the previous `InputNumber` used, so
 * the card modals' debounced autosave and re-analyze behave exactly as before.
 */
import { computed, ref, watch } from "vue";
import { formatMoney, parseMoney, toEditableText } from "../../utils/money";

const props = defineProps<{
  /** In *thousands* when `inThousands`, otherwise in dollars. */
  modelValue: number | null;
  label: string;
  placeholder?: string;
  min?: number;
  max?: number;
  required?: boolean;
  disabled?: boolean;
  /**
   * The value is stored in thousands: display it ×1000, emit ÷1000, and turn
   * on the "a bare number under 1,000 means thousands" typing shortcut.
   */
  inThousands?: boolean;
}>();

const emit = defineEmits(["update:modelValue"]);

const focused = ref(false);
/** What the user is typing. Only authoritative while focused. */
const draft = ref("");

/** The bound value expressed in dollars, whatever unit it is stored in. */
const dollars = computed(() =>
  props.modelValue == null
    ? null
    : props.inThousands
      ? props.modelValue * 1000
      : props.modelValue,
);

/** Re-seed the draft when the value changes underneath us (deal switched). */
watch(dollars, (next) => {
  if (!focused.value) draft.value = toEditableText(next);
});

const displayText = computed(() =>
  focused.value ? draft.value : formatMoney(dollars.value),
);

/** Live interpretation of the draft, shown as a hint while typing. */
const parsed = computed(() =>
  parseMoney(draft.value, props.inThousands === true),
);

/**
 * Show the hint only when the reading isn't self-evident — i.e. when a `k`/`m`
 * suffix or the <1000 rule scaled what they typed. Echoing "= $50,500" back at
 * someone who literally typed 50500 is just noise.
 */
const hint = computed(() =>
  focused.value && parsed.value.scaled && parsed.value.dollars != null
    ? `= ${formatMoney(parsed.value.dollars)}`
    : "",
);

const onFocus = (e: FocusEvent) => {
  draft.value = toEditableText(dollars.value);
  focused.value = true;
  // Select everything so typing replaces the old number, which is what you
  // want ~always on a field like this.
  (e.target as HTMLInputElement).select();
};

/** Parse, clamp, and write back — then let the formatted view take over. */
const commit = () => {
  focused.value = false;
  const { dollars: parsedDollars } = parseMoney(
    draft.value,
    props.inThousands === true,
  );
  if (parsedDollars == null) {
    emit("update:modelValue", null);
    return;
  }
  let next = props.inThousands ? parsedDollars / 1000 : parsedDollars;
  if (props.min != null) next = Math.max(props.min, next);
  if (props.max != null) next = Math.min(props.max, next);
  emit("update:modelValue", next);
};

const onKeydown = (e: KeyboardEvent) => {
  if (e.key === "Enter") {
    (e.target as HTMLInputElement).blur();
  } else if (e.key === "Escape") {
    // Abandon the edit and restore what was there.
    draft.value = toEditableText(dollars.value);
    (e.target as HTMLInputElement).blur();
  }
};
</script>

<template>
  <div class="flex flex-col gap-1.5">
    <!-- The hint shares the label's row rather than taking one of its own, so
         a money field is exactly as tall as every other input beside it and
         nothing shifts when the hint appears mid-typing. -->
    <div class="flex justify-between items-baseline gap-2">
      <label
        class="text-sm font-medium text-gray-700"
        :class="{
          'after:content-[\'*\'] after:ml-0.5 after:text-red-500': required,
        }"
      >
        {{ label }}
      </label>
      <span v-if="hint" class="text-xs font-medium text-blue-600">{{ hint }}</span>
    </div>
    <input
      type="text"
      inputmode="decimal"
      autocomplete="off"
      :value="displayText"
      :placeholder="placeholder"
      :disabled="disabled"
      class="w-full bg-white border border-gray-300 rounded-lg px-3 py-2 text-gray-900 placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 transition-all hover:bg-gray-50 disabled:bg-gray-100 disabled:text-gray-400"
      @focus="onFocus"
      @blur="commit"
      @input="draft = ($event.target as HTMLInputElement).value"
      @keydown="onKeydown"
    />
  </div>
</template>
