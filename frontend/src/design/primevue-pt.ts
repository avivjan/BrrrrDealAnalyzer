/**
 * The application-wide PrimeVue pass-through preset.
 *
 * PrimeVue runs unstyled here, so a component arrives with structure and no
 * appearance; every class it wears comes from a `pt` section. Until now those
 * sections were written inline at each call site, which meant the slider's
 * accent colour lived in `SliderField.vue`, the toggle's in `DealInputsForm.vue`,
 * and a colour change had to be chased through templates. Registering the
 * preset once in `main.ts` makes each primitive look the same everywhere and
 * puts its colours on the design tokens.
 *
 * It is installed with `ptOptions: { mergeSections: true, mergeProps: true }`,
 * so a component may still add a local `pt` for something genuinely local
 * without losing the preset underneath it.
 *
 * The classes below are the ones these components already rendered, with three
 * deliberate changes and nothing else:
 *
 * - `blue-500` / `blue-300` / `gray-400` become `primary` / `ring` /
 *   `fg-muted/60`, so the accent follows `tokens.css`.
 * - The slider handle grows from 20 px to 24 px — WCAG 2.5.8 Target Size
 *   (Minimum) is 24 CSS px for pointer targets on the web, and the old thumb
 *   missed it. The negative margins grow with it to keep the thumb centred.
 * - Its focus ring moves from `focus:` to `focus-visible:`, so dragging with a
 *   mouse no longer leaves a ring behind while keyboard focus still shows one.
 */
import type { PrimeVuePTOptions } from "primevue/config";

/**
 * The default look for an `InputNumber` that does not dress its own field.
 *
 * Both current call sites (`NumberInput.vue`, `SliderField.vue`) pass their own
 * `inputClass` — one full width, one a narrow right-aligned box — so for them
 * the section below deliberately contributes nothing and their markup is
 * unchanged by the preset. This is the baseline a *new* call site inherits.
 */
const INPUT_FIELD_BASE =
  "w-full bg-surface border border-line rounded-ctl px-3 py-2 text-fg " +
  "placeholder:text-fg-muted focus:outline-none focus-visible:ring-2 " +
  "focus-visible:ring-ring transition-all hover:bg-surface-muted";

export const primevuePt = {
  slider: {
    // The track itself keeps coming from the call site's own `class`, which is
    // where its width and height belong; only the fill is the preset's.
    range: {
      class: "bg-primary h-full rounded-full absolute top-0 left-0",
    },
    handle: {
      class:
        "bg-white border-2 border-primary w-6 h-6 rounded-full absolute top-1/2 " +
        "-mt-3 -ml-3 shadow-md hover:scale-110 transition-transform " +
        "focus:outline-none focus-visible:ring-2 focus-visible:ring-ring",
    },
  },
  toggleswitch: {
    // Root and handle are intentionally absent: the switch's size and knob come
    // from elsewhere in the markup, and giving them classes here would change
    // how the control looks, which this phase does not do.
    slider: ({ props }) => ({
      class: props.modelValue ? "bg-primary" : "bg-fg-muted/60",
    }),
  },
  inputnumber: {
    pcInputText: {
      root: ({ parent }) =>
        parent.props.inputClass ? {} : { class: INPUT_FIELD_BASE },
    },
  },
} satisfies PrimeVuePTOptions;
