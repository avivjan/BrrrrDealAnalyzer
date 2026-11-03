import { BRRRR_FORM_FIELDS, BRRRR_PAYLOAD, expect, fillForm, test } from '../fixtures';
import { fieldInput, fieldRoot, openTabOf, typeInto } from '../fixtures/form';

/**
 * Each monthly reserve of a regular year (vacancy, maintenance, CapEx, management) is a
 * percentage of the rent or dollars per month, through the % | $ pill in its label row.
 * Switching to $ seeds the dollars with what the percentage gives today (5% of $2,600 =
 * $130); typing $75 makes that the reserve, and the muted line reads the percentage back.
 */
test('a monthly reserve can be typed in dollars and switched back to a percentage of the rent', async ({ page }) => {
  await page.goto('/analyze');
  await expect(page.getByTestId('form.root')).toBeVisible();
  await fillForm(page, BRRRR_FORM_FIELDS, BRRRR_PAYLOAD);

  await openTabOf(page, 'vacancyPercent');
  const vacancy = fieldRoot(page, 'vacancyPercent');
  await expect(vacancy.locator('[data-part="other-unit"]')).toHaveText('of rent · ≈ $130/mo');
  await vacancy.getByRole('radio', { name: 'Dollars per month' }).click();
  await expect(vacancy.getByRole('radio', { name: 'Dollars per month' })).toHaveAttribute('aria-checked', 'true');
  await expect(fieldInput(page, 'vacancyPercent')).toHaveValue('$130');

  await typeInto(fieldInput(page, 'vacancyPercent'), '75');
  await expect(vacancy.locator('[data-part="other-unit"]')).toHaveText('per month · ≈ 2.88% of rent');

  await vacancy.getByRole('radio', { name: 'Percent of rent' }).click();
  await expect(vacancy.getByRole('radio', { name: 'Percent of rent' })).toHaveAttribute('aria-checked', 'true');
  await expect(fieldInput(page, 'vacancyPercent')).toHaveValue('2.88%');
});

test('the insurance bill at purchase is on Buy, and the regular year after the refi on Rent & Holding', async ({ page }) => {
  await page.goto('/analyze');
  await expect(page.getByTestId('form.root')).toBeVisible();
  const owningTab = (name: string) => fieldRoot(page, name).locator('xpath=ancestor-or-self::*[@data-form-tab]').first();
  await expect(owningTab('annual_insurance')).toHaveAttribute('data-form-tab', 'buy');
  await expect(owningTab('insurancePurchaseBillPaymentTiming')).toHaveAttribute('data-form-tab', 'buy');
  await expect(owningTab('monthlyInsuranceAfterRefi')).toHaveAttribute('data-form-tab', 'rentHolding');
  await openTabOf(page, 'monthlyInsuranceAfterRefi');
  await expect(page.getByText('Regular year after the refi', { exact: true })).toBeVisible();
});
