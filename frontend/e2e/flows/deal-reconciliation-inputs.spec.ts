import {
  BRRRR_FORM_FIELDS,
  BRRRR_PAYLOAD,
  expect,
  fillForm,
  test,
} from '../fixtures';
import { fieldInput, openTabOf, setField } from '../fixtures/form';

/**
 * The deal-reconciliation inputs on the Analyze page, before any save.
 *
 * The rehab completes between the purchase closing and the tenant moving in: a
 * completion after the tenant date turns the field red with its reason, marks
 * the Rehab tab, and keeps Analyze & Save from sending anything until it is
 * fixed, exactly like a lowest ARV above the ARV.
 *
 * The insurance and tax pickers move the bills between the settlements and the
 * owner's pocket, so the inline settlement figures follow them.
 */

const AFTER_THE_TENANT = 'Rehab completion must be on or before the tenant-occupied date.';

test('a rehab completion after the tenant date is flagged and blocks the save until fixed', async ({
  page,
  api,
}) => {
  await page.goto('/analyze');
  await expect(page.getByTestId('form.root')).toBeVisible();
  await fillForm(page, BRRRR_FORM_FIELDS, BRRRR_PAYLOAD);

  // The default 45 days to the rehab completion is after a tenant on day 30.
  await setField(page, 'daysUntilRented', 30);

  const rehabCompletionField = page.getByTestId('form.field.daysUntilRehabCompleted');
  await openTabOf(page, 'daysUntilRehabCompleted');
  await expect(rehabCompletionField.locator('[data-part="error-message"]')).toHaveText(AFTER_THE_TENANT);
  await expect(page.getByTestId('form.tab.rehab.has-invalid-input')).toBeAttached();

  api.reset();
  await page.getByTestId('analyze.analyze-save').click();
  await expect(page.getByTestId('analyze.errors')).toContainText(AFTER_THE_TENANT);
  await expect(page.getByTestId('analyze.modal')).toHaveCount(0);
  await api.expectNoRequests('an invalid rehab completion must not reach the server');

  await setField(page, 'daysUntilRehabCompleted', 30); // the same day as the tenant is allowed
  await expect(rehabCompletionField.locator('[data-part="error-message"]')).toHaveCount(0);
  await expect(page.getByTestId('form.tab.rehab.has-invalid-input')).toHaveCount(0);
});

test('the insurance and tax pickers move the bills between the settlements and the pocket', async ({
  page,
}) => {
  await page.goto('/analyze');
  await expect(page.getByTestId('form.root')).toBeVisible();
  await fillForm(page, BRRRR_FORM_FIELDS, BRRRR_PAYLOAD);
  const insuranceBill = BRRRR_PAYLOAD.annual_insurance as number;
  // "$12,360.42" or "-$1,200" as the figure shows it, back to a number.
  const figureValue = async (testId: string) => {
    const shown = (await page.getByTestId(testId).locator('[data-part="value"]').textContent()) ?? '';
    return Number(shown.replace(/[$,\s]/g, ''));
  };

  // Insurance at purchase: inside the purchase closing by default, then outside it.
  await openTabOf(page, 'purchasePrice');
  const closingCostsBuyInside = await figureValue('form.auto.closingCostsBuyTotal');
  await openTabOf(page, 'annual_insurance');
  await page.getByTestId('form.field.insurancePurchaseBillPaymentTiming').locator('select').selectOption('outside_purchase_closing');
  await openTabOf(page, 'purchasePrice');
  await expect.poll(() => figureValue('form.auto.closingCostsBuyTotal')).toBeCloseTo(closingCostsBuyInside - insuranceBill, 2);

  // Insurance at refi: inside the refi closing by default (off the wire), then outside it.
  await openTabOf(page, 'arv_in_thousands');
  const wireWithTheInsuranceInside = await figureValue('form.auto.cashOutWire');
  await page.getByTestId('form.field.insuranceRefiBillPaymentTiming').locator('select').selectOption('outside_refi_closing');
  await expect.poll(() => figureValue('form.auto.cashOutWire')).toBeCloseTo(wireWithTheInsuranceInside + insuranceBill, 2);

  // The refi lender collecting the whole tax bill takes it off the wire.
  const wireBeforeTheTaxLump = await figureValue('form.auto.cashOutWire');
  await page.getByTestId('form.field.propertyTaxCollectionAtRefi').locator('select').selectOption('full_tax_bill_collected_at_refi');
  await expect(fieldInput(page, 'propertyTaxLumpSumAtRefiClosing')).toBeVisible();
  await expect.poll(() => figureValue('form.auto.cashOutWire'))
    .toBeCloseTo(wireBeforeTheTaxLump - (BRRRR_PAYLOAD.annual_property_taxes as number), 2);
});

test('the rehab completion box shakes once when its message appears @motion', async ({ page, settle }, testInfo) => {
  test.skip(testInfo.project.name !== 'chromium-motion', 'the shake is a GSAP tween; the other projects run with animations off');
  await page.goto('/analyze');
  await expect(page.getByTestId('form.root')).toBeVisible();
  // Typed on its own (visible) tab: 100 days is after the default 90 to the tenant.
  await setField(page, 'daysUntilRehabCompleted', 100);
  await expect(page.getByTestId('form.field.daysUntilRehabCompleted').locator('[data-part="error-message"]')).toBeVisible();

  const transformOfTheBox = () =>
    page.evaluate(() => {
      // The number box's PrimeVue root carries the shake (the field's outer wrapper shares its data-part).
      const box = document.querySelector('[data-testid="form.field.daysUntilRehabCompleted"] span[data-part="input"]') as HTMLElement;
      return getComputedStyle(box).transform;
    });
  await page.clock.runFor(100);
  expect(await transformOfTheBox()).not.toBe('none');
  await settle(1000);
  expect(['none', 'matrix(1, 0, 0, 1, 0, 0)']).toContain(await transformOfTheBox());
});
