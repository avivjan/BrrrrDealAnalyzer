import { expect, type Locator, type Page } from '@playwright/test';
import { IN_THOUSANDS_FIELDS } from './payloads';

/**
 * Typing into `DealInputsForm`.
 *
 * The form is built from two input primitives that differ in one way that
 * matters to a spec:
 *
 *  - `MoneyInput` is a plain `<input type="text">` carrying `data-part=input`
 *    *on the input itself*. It commits on blur and reads a bare number under
 *    1,000 as thousands, so a field stored in thousands has to be typed in
 *    real dollars (`200` stored → type `200000`).
 *  - `NumberInput` / `SliderField` / `DaysUntilRefiField` wrap PrimeVue's
 *    `InputNumber`, whose root is a `<span>`; `data-part=input` lands on that
 *    span and the real `<input>` is inside it. These carry no unit scaling.
 *
 * `locator('input')` scoped to the field's `data-testid` resolves to exactly
 * one element for all four primitives (the slider renders no input), which is
 * why it is preferred here over a bare `[data-part=input]` — the addendum's
 * warning is about the PrimeVue span, and this never selects it.
 */

export function fieldRoot(page: Page, name: string): Locator {
  return page.getByTestId(`form.field.${name}`);
}

export function fieldInput(page: Page, name: string): Locator {
  return fieldRoot(page, name).locator('input');
}

/** True when the field is a plain `MoneyInput` rather than a PrimeVue one. */
async function isPlainInput(page: Page, name: string): Promise<boolean> {
  return (await fieldRoot(page, name).locator('input[data-part="input"]').count()) > 0;
}

/** The text a money field must be given to end up storing `stored`. */
export function moneyText(name: string, stored: number): string {
  return String(IN_THOUSANDS_FIELDS.has(name) ? stored * 1000 : stored);
}

/**
 * Replace an input's contents with `text` and commit it, by real keystrokes.
 *
 * `fill()` is wrong for these fields, not merely slower. `MoneyInput` re-seeds
 * its draft from the bound value on `focus`, and the Vue re-render that
 * follows reassigns `input.value` — which collapses the selection `fill()` had
 * just made, so the typed text lands *appended* to the old one (`10000` +
 * `6000` = a $100,006,000 closing cost). Select-all-then-type is immune,
 * because each step is its own round-trip long after that render, and it is
 * also what PrimeVue's masked `InputNumber` expects.
 */
export async function typeInto(input: Locator, text: string): Promise<void> {
  await expect(input).toBeVisible();
  await input.click();
  await input.press('ControlOrMeta+a');
  await input.press('Backspace');
  await input.pressSequentially(text);
  await input.blur();
}

/** Type a value into one deal-input field, scaling money fields as needed. */
export async function setField(
  page: Page,
  name: string,
  value: number,
): Promise<void> {
  const plain = await isPlainInput(page, name);
  await typeInto(fieldInput(page, name), plain ? moneyText(name, value) : String(value));
}

/** Fill a whole payload, in the given field order. */
export async function fillForm(
  page: Page,
  fields: readonly string[],
  payload: Record<string, unknown>,
): Promise<void> {
  for (const name of fields) {
    const value = payload[name];
    if (typeof value !== 'number') continue;
    await setField(page, name, value);
  }
}
