import {
  BRRRR_FORM_FIELDS,
  BRRRR_PAYLOAD,
  expect,
  fillForm,
  test,
} from '../fixtures';
import { fieldInput, openTabOf } from '../fixtures/form';

/**
 * The Seller Tax Credit is a result with a pencil: typing the credit off the
 * settlement statement overrides the proration, and this year's tax bill (one
 * shared field, read on the Buy tab beside the credit and on Rent & Holding)
 * stays as typed, because the bill paid on Nov 30 is its own figure. "auto"
 * puts the proration back. The fixture closes on 2026-09-04 (see
 * `fixtures/clock.ts`): 246 seller days of 365, so a $3,600 bill prorates to a
 * $2,426.30 credit.
 */
test('typing the seller tax credit overrides the proration and keeps the tax bill', async ({
  page,
}) => {
  await page.goto('/analyze');
  await expect(page.getByTestId('form.root')).toBeVisible();
  await fillForm(page, BRRRR_FORM_FIELDS, BRRRR_PAYLOAD);

  await openTabOf(page, 'purchasePrice'); // the Buy tab
  const figure = page.getByTestId('form.auto.sellerTaxCredit');
  await expect(figure.locator('[data-part="value"]')).toHaveText('$2,426.30');
  await expect(fieldInput(page, 'annualPropertyTaxesBuyClone')).toHaveValue('$3,600');

  await figure.locator('[data-part="edit"]').click();
  const box = figure.locator('[data-part="edit-input"]');
  await expect(box).toBeFocused();
  await box.press('ControlOrMeta+a');
  await box.pressSequentially('2410.45');
  await box.press('Enter');

  await expect(figure.locator('[data-part="value"]')).toHaveText('$2,410.45');
  await expect(fieldInput(page, 'annualPropertyTaxesBuyClone')).toHaveValue('$3,600');
  const override = page.getByTestId('form.field.sellerTaxCreditAtPurchaseClosing');
  await expect(override).toContainText('the proration gives $2,426.30');

  // The Rent & Holding box is the same field, on another (hidden) tab: untouched.
  await openTabOf(page, 'annual_property_taxes');
  await expect(fieldInput(page, 'annual_property_taxes')).toHaveValue('$3,600');

  await openTabOf(page, 'purchasePrice');
  await override.locator('[data-part="reset"]').click();
  await expect(figure.locator('[data-part="value"]')).toHaveText('$2,426.30');
  await expect(override).toHaveCount(0);
});
