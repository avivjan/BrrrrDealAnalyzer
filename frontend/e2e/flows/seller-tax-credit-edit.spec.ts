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
 * settlement statement back-solves Annual Taxes, and the one shared field is
 * read in two places (the Buy clone beside the credit, the Rent & Holding box).
 * The fixture closes on 2026-09-04 (see `fixtures/clock.ts`): 246 seller days
 * of 365, so $3,600 of taxes is a $2,426.30 credit and a typed $4,852.60 is
 * $7,200 of taxes.
 */
test('typing the seller tax credit adjusts Annual Taxes in both places', async ({
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
  await box.pressSequentially('4852.60');
  await box.press('Enter');

  await expect(figure.locator('[data-part="value"]')).toHaveText('$4,852.60');
  await expect(fieldInput(page, 'annualPropertyTaxesBuyClone')).toHaveValue('$7,200');

  // The Rent & Holding box is the same field, on another (hidden) tab.
  await openTabOf(page, 'annual_property_taxes');
  await expect(fieldInput(page, 'annual_property_taxes')).toHaveValue('$7,200');
});
