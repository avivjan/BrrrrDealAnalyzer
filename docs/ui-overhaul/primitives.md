# Presentational primitives

Thirteen components under `frontend/src/components/ui/`, re-exported from
`frontend/src/components/ui/index.ts`. They hold no state, reach no store, read
no route and own no behaviour: they take props and slots and render tokens.

They exist so that Phase 3 can restyle a view by changing a tag, not by moving
logic. Everything on this page follows from that one goal.

## The four rules that apply to all of them

**1. Copy travels through slots, never through props.** A primitive never
hard-codes a word the user reads, and no label, title or message is a string
prop. The behaviour-freeze gate `G4b` builds a text manifest from the *views*'
templates; the moment a caption moves into `<UiStatTile label="Cash flow">` it
disappears from that manifest and the gate reports a copy change that did not
happen. Visually hidden accessibility text *inside* a primitive is the one
exception — `UiStatTile`'s "negative", `UiField`'s "required" — because the gate
does not read primitive templates and that text is not the view's copy.

```vue
<!-- do -->
<UiStatTile tone="negative"><template #label>Cash flow</template>-$140</UiStatTile>
<!-- don't -->
<UiStatTile label="Cash flow" value="-$140" />
```

**2. `$attrs` reach the root element.** Every primitive sets
`inheritAttrs: false` and re-binds `$attrs` by hand, so `class` can go through
`cn()` (where `tailwind-merge` drops what the caller means to override) while
`data-testid`, `aria-*` and native listeners land on the real element. No
primitive calls `stopPropagation` or `preventDefault`, so a `@click` that moved
from a `div` to a `<UiCard>` still fires on the same DOM node.

Nothing that reads `$attrs` or `$slots` may be cached in a `computed`. Both are
evaluated during render — in a plain function or in the template itself — and
for two different reasons. `useAttrs()` returns a proxy that tracks a *read of a
key*, so spreading it while it holds no keys registers no dependency at all: a
computed caches that first empty object for the life of the component and
silently drops every attribute the parent binds later. Slots are not tracked at
all: `useSlots()` is a plain object Vue mutates in place, so a computed over
`$slots.error` freezes at whatever the first render saw and never notices the
parent starting or stopping to pass it. `UiCard.test.ts`, `UiField.test.ts` and
`UiModalPanel.test.ts` have the regressions.

**3. Tokens only.** `bg-surface`, `text-fg-muted`, `border-line`,
`rounded-ctl/card/panel`, `shadow-1/2/3`, `duration-fast`, `ease-standard`.
Never `gray-*`, `blue-*`, `indigo-*` or a hex literal. Focus is always
`focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring
focus-visible:ring-offset-2`.

**4. Behaviour stays in the view.** No primitive owns a click, a `v-model`, an
open/closed flag, focus, or the Escape key. A primitive that needed one would
change behaviour the moment a view adopted it, which is exactly what this phase
promises not to do.

## The primitives

Batch A (`UiButton`, `UiIconButton`, `UiCard`, `UiBadge`, `UiStatTile`) and
batch B (the other eight) are documented together; the split is only the order
they were written in.

---

### `UiButton`

The app's button. Deliberately thin: the parent keeps the click, the `disabled`
decision and every word.

| | |
|---|---|
| **Props** | `variant: 'primary' \| 'secondary' \| 'ghost' \| 'danger' \| 'brrrr' \| 'flip' \| 'tab'` (primary), `size: 'sm' \| 'md' \| 'lg'` (md), `loading?`, `block?`, `type: 'button' \| 'submit' \| 'reset'` (button), `active?` |
| **Slots** | `default` — the label |
| **Root** | `<button>`, `data-ui="button"` |

`variant="tab"` adds `role="tab"` and `aria-selected` from `active`; an explicit
`role` attribute still wins. `brrrr` is deliberately identical to `primary` —
the strategy's accent *is* the app's accent — and exists so a call site can say
what it means rather than which colour it wants.

```vue
<UiButton variant="brrrr" :loading="saving" :disabled="saving" @click="save">
  Save deal
</UiButton>
```

- **Do** keep passing `:disabled` when a click must not repeat.
- **Don't** expect `loading` to disable anything. It renders the spinner and
  sets `aria-busy`, and that is all. Several call sites want a spinner during a
  background refresh and still want the button pressable; guessing would change
  behaviour. This knowingly departs from the guideline below — double
  submission stays the parent's problem.
- **Don't** use `size="sm"` (24 px tall) for a primary phone target. It clears
  the WCAG 2.2 target-size floor exactly and nothing more.

> Checked against `"loading buttons disable spinner"` — *Interaction / Loading
> Buttons: prevent double submission during async actions. Do: disable button
> and show loading state.* And `"disabled states opacity"` — *Interaction /
> Disabled States. Do: reduce opacity and change cursor* (`disabled:opacity-50
> disabled:cursor-not-allowed`).

---

### `UiIconButton`

A square, icon-only button with a finger-sized hit area.

| | |
|---|---|
| **Props** | `label: string` (**required**), `size: 'sm' \| 'md'` (sm = 32 px, md = 40 px), `variant: 'ghost' \| 'secondary' \| 'danger'` (ghost), `type` |
| **Slots** | `default` — the icon |
| **Root** | `<button>`, `data-ui="icon-button"` |

`label` becomes `aria-label`. It is required at the type level *and* warned
about at runtime in dev, because Vue's own required-prop warning does not fire
for `label=""` — which is the shape this actually arrives in, from an
interpolated title that turned out empty.

The visual box stays 32/40 px so dense toolbars keep their rhythm; a transparent
`::before` grows the hit area to 44 px without moving a neighbour.

```vue
<UiIconButton label="Delete deal" variant="danger" @click="remove(deal.id)">
  <i class="pi pi-trash" aria-hidden="true" />
</UiIconButton>
```

- **Do** write a label that says what the button *does* ("Delete deal"), not
  what it looks like ("Trash").
- **Don't** wrap it in extra padding to make it tappable; the `::before` already
  did, and padding would move the icons apart.

> Checked against `"touch target size"` — *Touch / Touch Target Size: use 44pt
> on iOS and 48dp on Android; for web use the separate WCAG Target Size rule.
> Don't: `w-6 h-6` buttons.*

---

### `UiCard`

The bordered, rounded surface with an optional header and footer.

| | |
|---|---|
| **Props** | `tone: 'surface' \| 'muted' \| 'elevated'` (surface), `interactive?`, `padding: 'none' \| 'sm' \| 'md' \| 'lg'` (md), `as: string` (`'div'`) |
| **Slots** | `header`, `default` (body), `footer` |
| **Root** | `<component :is="as">`, `data-ui="card"` |

Padding lands on the *regions*, not on the root: a card with a header needs a
rule that spans the full shell, and a padded root cannot draw one without a
negative margin. `as` exists because a card is a shape, not a meaning — the same
shell is a `div` in a grid, a `section` on a page and an `li` in a list.

```vue
<UiCard as="li" tone="elevated" interactive @click="open(deal)">
  <template #header><h3 class="font-semibold">{{ deal.address }}</h3></template>
  {{ deal.city }}
</UiCard>
```

- **Do** pass `as` to keep the outer tag the view already had.
- **Don't** put an `interactive` card inside `<VueDraggable>`. SortableJS owns
  the DOM of its `v-for` children in `MyDeals`, `BoughtDeals` and
  `PipelineTemplateEditor`; a wrapper, a `:key` remount or a hover transform on
  a node it is mid-drag over changes drag behaviour, and `BoughtDeals` has no
  coarse-pointer fallback to hide the damage. A non-interactive `UiCard` that
  replaces the existing child element one-for-one is fine.

---

### `UiBadge`

A status pill: tinted ground, token ink, the caller's word.

| | |
|---|---|
| **Props** | `tone: 'neutral' \| 'primary' \| 'positive' \| 'negative' \| 'warning' \| 'info'` (neutral), `size: 'sm' \| 'md'` (sm), `dealType?: 'BRRRR' \| 'FLIP'` |
| **Slots** | `default` — the label |
| **Root** | `<span>`, `data-ui="badge"` |

`dealType` prepends an icon (`pi-home` / `pi-dollar`, `aria-hidden`) and picks
the tone, overriding an explicit `tone` rather than letting the two disagree.
`info` is the one tone that is not `bg-x/10 text-x`: the palette has no semantic
info colour, and `chart-4` as 12 px ink is under AA, so it gets a wash plus a
ring and keeps `fg` as its ink. The badge carries no transition classes — it has
no hover, focus or active state to travel between.

```vue
<UiBadge :deal-type="deal.strategy">{{ deal.strategy }}</UiBadge>
```

- **Do** keep the strategy word in the slot even though the icon repeats it. The
  icon is the non-colour channel, not a replacement for the label.
- **Don't** rely on tone alone to tell two states apart.

> Checked against `"badge status color not only"` — *Accessibility / Color Only:
> don't convey information by color alone. Do: use icons/text in addition to
> color.*

---

### `UiStatTile`

One number and its caption — the unit the stats bars and analysis panels are
built from.

| | |
|---|---|
| **Props** | `tone: 'neutral' \| 'positive' \| 'negative' \| 'warning'` (neutral), `size: 'sm' \| 'md'` (sm), `label?: string` (fallback for the slot) |
| **Slots** | `label`, `default` (the value), `hint` |
| **Root** | `<div>`, `data-ui="stat-tile"` |

Every non-neutral tone carries an arrow or a warning triangle *and* a visually
hidden word, so "this is negative" survives a colour-blind reader, a greyscale
print and a screen reader. The value is `tabular`, so a figure ticking from
$1,199 to $1,240 changes its digits without changing its width. Like `UiBadge`
it carries no transitions: it is a read-only readout.

```vue
<UiStatTile tone="positive">
  <template #label>Monthly cash flow</template>
  {{ formatMoney(deal.cashFlow) }}
  <template #hint>after PITI</template>
</UiStatTile>
```

- **Do** prefer the `#label` slot; the `label` prop is a convenience for plain
  strings and the slot wins when both are given.
- **Don't** hand it a pre-coloured value — the tone owns the colour, and a red
  `<span>` inside would defeat the icon-plus-word pairing.

---

### `UiField`

The wrapper around one form control: its label, its helper text, its error, and
the ids that tie them together.

| | |
|---|---|
| **Props** | `id?: string` (else `useId()`), `required?`, `invalid?`, `inline?` |
| **Slots** | `label`; `default` — **scoped**, receives `{ id, describedBy, invalid }`; `helper`; `error` |
| **Root** | `<div>`, `data-ui="field"` |

**The control is the parent's.** The default slot is scoped and the call site
renders its own `<input>`, `<InputNumber>` or `<MoneyInput>` inside it, binding
the three values it is handed. Every `v-model`, every `@blur` and every
formatting rule therefore stays in the template that already owns it.

`describedBy` lists only the messages actually on screen, helper first and error
second — the order they are read in — and is `undefined` when there are none, so
the binding drops the attribute rather than pointing at an empty node.

```vue
<UiField required :invalid="!!errors.price">
  <template #label>Purchase price</template>
  <template #default="{ id, describedBy, invalid }">
    <MoneyInput :id="id" v-model="form.price"
                :aria-describedby="describedBy" :aria-invalid="invalid" />
  </template>
  <template #helper>Before closing costs</template>
  <template #error>{{ errors.price }}</template>
</UiField>
```

- **Do** bind all three scoped values. Binding `id` alone loses the error
  announcement.
- **Don't** pass an `id` unless something outside needs it; the generated one is
  unique per app and never collides.
- **Don't** expect the field to render a control, validate anything, or set
  `aria-invalid` itself.

> Checked against `"error placement aria-describedby"` — *Forms / Error
> Placement: show a specific error below the input and reference it with
> `aria-describedby`*, and *Accessibility / Error Messages: use `aria-live` or
> `role=alert` for errors* (the error paragraph is `role="alert"`).

---

### `UiModalPanel`

The panel a modal is drawn on. **The overlay is not here.**

| | |
|---|---|
| **Props** | `size: 'sm' \| 'md' \| 'lg' \| 'xl' \| 'full'` (md), `labelledBy?: string` |
| **Slots** | `header`, `default` (body), `footer` |
| **Root** | `<div role="dialog" aria-modal="true">`, `data-ui="modal-panel"` |

Sizes are `max-w-md / lg / 3xl / 5xl`; `full` is the phone treatment — edge to
edge, `h-[100svh]`, back to a centred panel from `md` up.

The overlay `div`, its `@click.self`, the Escape key and the `v-if` that mounts
the thing are behaviour and stay in the parent. This component registers **no
listener** on `document` or `window`, has no `Teleport` and manages no focus; a
test spies on both `addEventListener`s to keep it that way. Focus trapping is a
later phase's deliberate, single-place decision.

Without `labelledBy`, the header slot is wrapped in an `<h2>` the root points
at. With `labelledBy`, the caller owns the heading and the header slot renders
bare — which is what a header holding a title *and* a close button needs, since
a button inside the `<h2>` would become part of the dialog's spoken name.

```vue
<div v-if="open" class="fixed inset-0 grid place-items-center bg-fg/40 p-4"
     @click.self="close">
  <UiModalPanel size="lg">
    <template #header>Edit deal</template>
    <DealForm v-model="draft" />
    <template #footer>
      <UiButton variant="ghost" @click="close">Cancel</UiButton>
      <UiButton @click="save">Save</UiButton>
    </template>
  </UiModalPanel>
</div>
```

- **Do** keep the overlay, the `v-if` and the Escape handler exactly where they
  already are.
- **Do** use `labelledBy` when the header needs its own controls.
- **Don't** add a focus trap at a call site. One inconsistent trap is worse than
  none; it lands app-wide in a later phase.

> Checked against `"modal escape routes"` — the only guideline returned is
> *Interaction / Focus States: keyboard focus, including controls inside a
> modal, needs a visible indicator*, which the global `:focus-visible` rule in
> `frontend/src/assets/main.css` already provides. Nothing in the corpus
> requires the panel itself to own an escape route, which is consistent with
> leaving Escape in the parent.

---

### `UiSectionHeader`

A title, an optional line under it, and the controls that belong to the section.

| | |
|---|---|
| **Props** | `as: 'h1' \| 'h2' \| 'h3' \| 'h4'` (h2) |
| **Slots** | `default` (title), `subtitle`, `actions` |
| **Root** | `<div class="flex items-start justify-between gap-3">`, `data-ui="section-header"` |

The type scale follows the heading level rather than a separate `size` prop: a
heading that looks like an `h1` and announces as an `h3` is exactly the failure
this prevents. The title column is `min-w-0`, so a long title truncates instead
of shoving the actions off the row.

```vue
<UiSectionHeader as="h1">
  My deals
  <template #subtitle>{{ deals.length }} active</template>
  <template #actions><UiButton @click="add">New deal</UiButton></template>
</UiSectionHeader>
```

- **Do** pick `as` from the page's outline, not from the size you want.
- **Don't** put a form control in `#actions` — it is a row of buttons, not a
  toolbar with state.

---

### `UiEmptyState`

The placeholder for a list with nothing in it.

| | |
|---|---|
| **Props** | `icon?: string` (a `pi pi-*` class, rendered `aria-hidden`) |
| **Slots** | `default` (title), `description`, `actions` |
| **Root** | `<div>`, `data-ui="empty-state"` |

Dashed, not solid: an empty *solid* card reads as content that failed to load,
while a dashed outline says the box is meant to be empty. The icon is decorative
and hidden — it repeats what the title says, and an announced icon name is
noise.

```vue
<UiEmptyState icon="pi pi-inbox">
  No deals yet
  <template #description>Analyze a property to add your first one.</template>
  <template #actions><UiButton @click="add">Add a deal</UiButton></template>
</UiEmptyState>
```

- **Do** give it the action that fills it. An empty state without a next step is
  a dead end.
- **Don't** use it for an error. "Nothing here" and "something broke" are
  different messages and want different treatments.

> Checked against `"empty states"` — *Feedback / Empty States: guide users when
> no content exists. Do: show helpful message and action. Don't: blank empty
> screens.*

---

### `UiSkeleton`

The grey shape that stands in for content still loading.

| | |
|---|---|
| **Props** | `lines: number` (1), `rounded: 'ctl' \| 'card' \| 'full'` (ctl) |
| **Slots** | none |
| **Root** | `<div aria-hidden="true">`, `data-ui="skeleton"` |

Size comes from the caller's own classes on the root — a skeleton is only useful
at the size of the thing it replaces, and only the call site knows that. One
line fills its box; several are text lines with a short last one, so the block
reads as prose rather than as a table.

It is `aria-hidden` and wordless on purpose: a screen reader gains nothing from
"loading, loading, loading". The busy announcement belongs on the region that
knows what it is waiting for (`aria-busy` on the container).

```vue
<div :aria-busy="loading">
  <UiSkeleton v-if="loading" :lines="3" class="w-full" />
  <DealList v-else :deals="deals" />
</div>
```

- **Do** match the skeleton's box to the real content's box, or the layout jumps
  when it resolves.
- **Don't** add a bespoke reduced-motion guard. The global
  `@media (prefers-reduced-motion: reduce)` rule at the bottom of
  `frontend/src/assets/main.css` already cuts every animation to 0.01 ms, so
  `animate-pulse` becomes a flat grey block with no extra code.

> Checked against `"skeleton loading reduced motion"` — *Animation / Reduced
> Motion: respect the user's motion preferences* and *Feedback / Loading
> Indicators: preserve layout, focus and accessible busy status. Good: stable
> skeleton or progress with `aria-busy`.*

---

### `UiSaveStatus`

The small marker beside an autosaving control.

| | |
|---|---|
| **Props** | `status: 'idle' \| 'saving' \| 'saved' \| 'error'` (idle) |
| **Slots** | `default` — the label, rendered for every status but `idle` |
| **Root** | `<span role="status" aria-live="polite" :data-state>`, `data-ui="save-status"` |

Icons and tones: `saving` → `pi-spinner pi-spin`, muted; `saved` → `pi-check`,
positive; `error` → `pi-exclamation-circle`, negative.

**Idle renders an empty span, not nothing.** The element stays in the layout
with `min-h-4` reserved, so the row does not jump the instant a save starts —
which is precisely when the user is typing into it. A `hidden` attribute or a
`v-if` in the parent would both reflow at that moment.

```vue
<UiSaveStatus :status="saveState">
  {{ saveState === 'error' ? "Couldn't save" : 'Saved' }}
</UiSaveStatus>
```

- **Do** keep the words in the view. One screen can say "Saved" and another "All
  changes saved" with no prop, and the copy gate keeps seeing both.
- **Don't** wrap it in a `v-if`. That gives back the layout shift the empty idle
  span exists to prevent.

---

### `UiTabs`

The inset track a row of tabs sits in. A container and nothing more.

| | |
|---|---|
| **Props** | `ariaLabel?: string` |
| **Slots** | `default` — the tabs |
| **Root** | `<div role="tablist">`, `data-ui="tabs"` |

The tabs stay in the view's own `v-for`, as `UiButton variant="tab" :active`,
because which tab is selected — and what selecting one does — is behaviour.
`overflow-x-auto` rather than `flex-wrap`: six filters on a phone should scroll
as one row, not restack into two and change the height of everything below.

```vue
<UiTabs aria-label="Deal type">
  <UiButton v-for="t in types" :key="t" variant="tab" :active="t === active"
            @click="active = t">
    {{ t }}
  </UiButton>
</UiTabs>
```

- **Do** pass `ariaLabel` when no visible heading already names the group.
- **Don't** replace the `v-for` with a `tabs` array prop. That deletes the
  view's loop and its interpolations, and the `G4`/`G4b` gates fail — correctly,
  because the copy really did move.

---

### `UiStepper`

The progress rail across a multi-step flow. A container, like `UiTabs`.

| | |
|---|---|
| **Props** | `count: number` (**required** — the number of steps), `compact?` |
| **Slots** | `default` — the steps |
| **Root** | `<ol role="list">`, `data-ui="stepper"` |

`count` is published as `--steps` and the columns are
`repeat(var(--steps), minmax(0, 1fr))`. `minmax(0, …)` — not `1fr` alone — is
what lets a long label ellipsise instead of stretching its column.

**The child contract:** each step is the view's own element (usually the `<li>`
it already had) carrying `data-step="done" | "active" | "todo"`. The component's
scoped CSS styles those children through `:slotted([data-step])` — the one hook
Vue offers onto markup a parent owns. It sets the colour per state, ellipsises
the label, and draws the connector as a `::before` inside the step's own box
(outside it, the `overflow: hidden` the ellipsis needs would clip it); the first
step gets neither connector nor indent. A `<li>` without `data-step` is left
entirely alone.

The label is truncated here, so **the view supplies the `title` attribute** that
reveals the full text — only the view has the string.

```vue
<UiStepper :count="steps.length">
  <li v-for="(step, i) in steps" :key="step.id" :title="step.name"
      :data-step="i < current ? 'done' : i === current ? 'active' : 'todo'">
    {{ step.name }}
  </li>
</UiStepper>
```

- **Do** keep the `v-for` and its children exactly as they were; only the
  enclosing tag and one attribute change.
- **Don't** pass a `steps` array prop, for the same reason as `UiTabs`.
- **Don't** forget `:title`; a truncated step name with no tooltip is
  unreadable.

> Checked against `"multi-step progress indicator"` — *Feedback / Progress
> Indicators: show progress for multi-step processes. Do: step indicators or
> progress bar.*

---

## Two things every primitive has to live with

### The 16 px floor on phones

Below 768 px, `frontend/src/assets/main.css` forces every `input`, `select` and
`textarea` to `font-size: 16px !important`. iOS Safari zooms the whole viewport
when a control smaller than 16 px takes focus and the user then has to pinch
their way back out; `!important` is the only thing that outranks a `text-xs`
utility sitting on the control.

So: **no primitive sizes a control below 16 px on mobile**, and none should try.
A `text-xs` on an input is simply overridden below 768 px and honoured above it,
which means a field that looks right on a phone and a desktop was designed at
two sizes on purpose, not by accident. `UiField` sets no font size on the
control at all — the control is the parent's.

### `hoverOnlyWhenSupported` is off until the end of Phase 3

`tailwind.config.js` deliberately does not enable it yet. Turning it on wraps
every `hover:` utility in `@media (hover: hover)`, which would hide the fourteen
controls this app reveals only on hover from every touch device.

Until the flag flips, `hover:` styles render on a touch device's tap-and-hold —
harmless for the enhancement kind (a colour, a shadow), fatal for the reveal
kind. **Any hover-only affordance must already ship a `touch:` counterpart**
(`touch:` is `@media (hover: none)`, defined in `tailwind.config.js`). The
primitives currently use hover only for enhancements — nothing is hidden behind
one — so none of them needs a counterpart today; a new primitive that hides
something behind `hover:` does.

## Two safe-area spellings

Both reach `env(safe-area-inset-bottom)`, and they are not interchangeable:

| Spelling | What it is | Where it comes from |
|---|---|---|
| `.safe-b` | a utility class that *sets* `padding-bottom: env(safe-area-inset-bottom)` | `@layer utilities` in `frontend/src/assets/main.css` |
| `pb-safe-b` | Tailwind's own `pb-*` utility against the `safe-b` spacing key | the `spacing` extension in `tailwind.config.js` |

**Prefer `pb-safe-b` in templates.** It is a normal `pb-*` utility, so
`tailwind-merge` can reason about it inside `cn()`, it composes with variants
(`md:pb-safe-b`), and it reads as padding rather than as a magic class. `.safe-b`
stays for the handful of places that want the raw declaration, and the `safe-t`,
`safe-l`, `safe-r` siblings exist in both spellings too.

One trap: `pb-safe-b` *replaces* a `py-*` bottom padding rather than adding to
it, and the inset is `0` on every device without a notch — so a footer written
`py-3 pb-safe-b` has no bottom padding at all on a laptop. `UiModalPanel` puts
`pb-safe-b` on the sticky footer *region* and the real padding on a box inside
it, so the inset is added below the padding instead of replacing it. Copy that
shape.

## One PrimeVue note, for whoever does Phase 3.4

`frontend/src/design/primevue-pt.ts` has an `inputnumber` section whose
`pcInputText.root` returns `{}` whenever the call site passes `inputClass` — and
both existing call sites do. **The preset therefore contributes nothing today.**

What it defines is what a *bare* `<InputNumber>` would get: a tokenised default
that does **not** match how `NumberInput` currently looks. Phase 3.4 has to
decide which of the two wins — either the preset becomes the shared look and the
`inputClass` call sites drop theirs, or the preset is deleted as dead
configuration. Adding a third bare `<InputNumber>` before that decision would
silently introduce a second input style.
