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
 *
 * Task 3.4 adds the fourth: `toggleswitch` now dresses its `root`, `input` and
 * `handle` as well. That is a visual change and a deliberate one — with only
 * `slider` themed, the switch rendered as a bare native checkbox beside a
 * zero-height div, so there was no switch to preserve.
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
    /*
     * The four sections are one control between them. PrimeVue renders
     *
     *   root  >  input[type=checkbox]  +  slider  >  handle
     *
     * and unstyled means all four arrive bare — which is why the switch was a
     * naked checkbox next to a zero-height `slider` div until now. `root` gives
     * the control its 44x24 box, `input` covers that whole box at zero opacity
     * so the native checkbox keeps the click, the focus and the `role=switch`
     * announcement, and `slider`/`handle` draw what is actually seen.
     *
     * The focus ring therefore has to travel from the input to the track:
     * `peer` on the input plus `peer-focus-visible:` on its next sibling is
     * exactly that, and keyboard-only because the input is a real control.
     */
    root: {
      class: "relative inline-flex h-6 w-11 shrink-0 items-center rounded-full",
    },
    input: {
      class: "peer absolute inset-0 z-10 m-0 h-full w-full cursor-pointer opacity-0",
    },
    slider: ({ props }) => ({
      class: [
        "absolute inset-0 rounded-full transition-colors duration-fast ease-standard",
        "peer-focus-visible:ring-2 peer-focus-visible:ring-ring peer-focus-visible:ring-offset-2",
        props.modelValue ? "bg-primary" : "bg-fg-muted/60",
      ].join(" "),
    }),
    // `bg-white`, like the slider handle above: a knob on a filled track reads
    // as white in either theme, where `bg-surface` would vanish into the track.
    handle: ({ props }) => ({
      class: [
        "absolute top-1/2 h-5 w-5 -translate-y-1/2 rounded-full bg-white shadow-1",
        "transition-transform duration-fast ease-standard",
        props.modelValue ? "translate-x-[1.375rem]" : "translate-x-0.5",
      ].join(" "),
    }),
  },
  inputnumber: {
    pcInputText: {
      root: ({ parent }) =>
        parent.props.inputClass ? {} : { class: INPUT_FIELD_BASE },
    },
  },
} satisfies PrimeVuePTOptions;
