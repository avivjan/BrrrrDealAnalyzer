import { expect, test } from '../fixtures';

/**
 * A deal that doesn't validate never reaches the network. `validateDealInputs`
 * runs before the save modal opens, so an empty form must produce a list of
 * messages, no modal, and — the part worth freezing — not one request.
 */

const EMPTY_BRRRR_ERRORS = [
  'Purchase price (in thousands) must be greater than 0.',
  'ARV (in thousands) must be greater than 0.',
  'Rent must be greater than 0.',
];

test('an invalid deal lists its problems and sends nothing', async ({
  page,
  api,
}) => {
  await page.goto('/analyze');
  await expect(page.getByTestId('form.root')).toBeVisible();

  // Everything before the click is page-load traffic; the claim is about what
  // the click does.
  api.reset();

  await page.getByTestId('analyze.analyze-save').click();

  await expect(page.getByTestId('analyze.errors')).toBeVisible();
  for (const [index, message] of EMPTY_BRRRR_ERRORS.entries()) {
    await expect(page.getByTestId(`analyze.error.${index}`)).toHaveText(message);
  }
  await expect(page.getByTestId(`analyze.error.${EMPTY_BRRRR_ERRORS.length}`)).toHaveCount(0);

  await expect(page.getByTestId('analyze.modal')).toHaveCount(0);
  await api.expectNoRequests('an invalid deal must not reach the server');
});
