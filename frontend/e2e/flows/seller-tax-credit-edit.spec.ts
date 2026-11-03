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
 * follows it: it becomes the bill whose proration gives that credit. "auto"
 * drops the typed credit, and the proration of the new bill gives the same
 * figure. The fixture clock reads 2026-09-04 (see `fixtures/clock.ts`) and a new
 * deal closes ten days after its contract (today), on 2026-09-14: 256 seller
 * days of 365, so a $3,600 bill prorates to a $2,524.93 credit.
 */
test('typing the seller tax credit overrides the proration and updates the tax bill to match', async ({
  page,
}) => {
  await page.goto('/analyze');
  await expect(page.getByTestId('form.root')).toBeVisible();
  await fillForm(page, BRRRR_FORM_FIELDS, BRRRR_PAYLOAD);

  await openTabOf(page, 'purchasePrice'); // the Buy tab
  const figure = page.getByTestId('form.auto.sellerTaxCredit');
  await expect(page.getByTestId('form.field.buyClosingDate').locator('input')).toHaveValue('2026-09-14');
  await expect(figure.locator('[data-part="value"]')).toHaveText('$2,524.93');
  await expect(fieldInput(page, 'annualPropertyTaxesBuyClone')).toHaveValue('$3,600');

  await figure.locator('[data-part="edit"]').click();
  const box = figure.locator('[data-part="edit-input"]');
  await expect(box).toBeFocused();
  await box.press('ControlOrMeta+a');
  await box.pressSequentially('2410.45');
  await box.press('Enter');

  await expect(figure.locator('[data-part="value"]')).toHaveText('$2,410.45');
  // 2,410.45 × 365 ÷ 256 seller days: the bill whose proration gives that credit.
  await expect(fieldInput(page, 'annualPropertyTaxesBuyClone')).toHaveValue('$3,436.77');
  const override = page.getByTestId('form.field.sellerTaxCreditAtPurchaseClosing');
  await expect(override).toContainText('the proration gives $2,410.45');

  // The Rent & Holding box is the same field, on another (hidden) tab: it follows too.
  await openTabOf(page, 'annual_property_taxes');
  await expect(fieldInput(page, 'annual_property_taxes')).toHaveValue('$3,436.77');

  await openTabOf(page, 'purchasePrice');
  await override.locator('[data-part="reset"]').click();
  await expect(figure.locator('[data-part="value"]')).toHaveText('$2,410.45');
  await expect(override).toHaveCount(0);
});
