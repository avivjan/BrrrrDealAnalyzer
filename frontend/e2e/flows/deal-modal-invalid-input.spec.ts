import { expect, test } from '../fixtures';
import { fieldInput, setField } from '../fixtures/form';

/**
 * A wrong input never fails silently again.
 *
 * Typing a Lowest ARV above the ARV used to leave the box showing the new
 * number, the result tiles showing the old analysis, and a "Save failed" chip
 * with no reason: the backend's 400 was swallowed. Now the field is outlined
 * and explains itself, the tab that holds it is marked, the tiles give way to
 * a notice, the chip says why nothing was saved, and not one request leaves
 * until the value is fixed — at which point everything resumes on its own.
 */

const CLOSE_ANYWAY_DIALOG =
  'These inputs are invalid and were not saved:\n- Lowest ARV cannot exceed ARV. (Refinance tab)\n\nClose anyway? They go back to their last saved values; your other changes are saved.';

async function openActiveDeal(page: import('@playwright/test').Page, dealId: string, settle: (ms: number) => Promise<void>) {
  await page.getByTestId(`mydeals.card.${dealId}`).click();
  await expect(page.getByTestId('mydeals.modal')).toBeVisible();
  // Past the 250 ms settle window, before the 500 ms analyze debounce.
  await settle(300);
}

test('a lowest ARV above the ARV pauses the modal, and a fix resumes it', async ({
  page,
  api,
  seed,
  settle,
}) => {
  const deal = await seed.seedActiveDeal('BRRRR', { section: 1, lowestArv: 300 });
  await page.goto('/my-deals');
  await openActiveDeal(page, deal.id, settle);
  await expect(page.getByTestId('mydeals.modal.result.cash_flow')).toBeVisible();
  api.reset();

  await setField(page, 'lowestArv', 400);

  const lowestArvField = page.getByTestId('form.field.lowestArv');
  await expect(lowestArvField.locator('[data-part="error-message"]')).toHaveText('Lowest ARV cannot exceed ARV.');
  await expect(fieldInput(page, 'lowestArv')).toHaveAttribute('aria-invalid', 'true');
  await expect(fieldInput(page, 'lowestArv')).toHaveClass(/ui-input-invalid/);
  await expect(page.getByTestId('form.tab.refinance.has-invalid-input')).toBeAttached();

  await expect(page.getByTestId('mydeals.modal.results-paused')).toBeVisible();
  await expect(page.getByTestId('mydeals.modal.results-paused')).toContainText('Results paused until the highlighted inputs are fixed.');
  await expect(page.getByTestId('mydeals.modal.results-paused.lowestArv')).toContainText('Lowest ARV cannot exceed ARV.');
  await expect(page.getByTestId('mydeals.modal.results-paused.lowestArv')).toContainText('Refinance tab');
  await expect(page.getByTestId('mydeals.modal.result.cash_flow')).toHaveCount(0);
  await expect(page.getByTestId('mydeals.modal.save-status')).toHaveAttribute('data-state', 'error');
  await expect(page.getByTestId('mydeals.modal.save-status')).toHaveText('Not saved — fix the highlighted inputs');

  // The message sits under the box: the ARV box beside it keeps the same top and height.
  const arvBox = (await fieldInput(page, 'arv_in_thousands').boundingBox())!;
  const lowestArvBox = (await fieldInput(page, 'lowestArv').boundingBox())!;
  expect(Math.abs(arvBox.y - lowestArvBox.y)).toBeLessThanOrEqual(1);
  expect(Math.abs(arvBox.height - lowestArvBox.height)).toBeLessThanOrEqual(1);

  // Past both debounces: nothing was analyzed, nothing was saved.
  await settle(2500);
  expect(api.matching((request) => request.method === 'POST' && request.path === '/analyze/brrr')).toHaveLength(0);
  expect(api.matching((request) => request.method === 'PUT')).toHaveLength(0);

  await setField(page, 'lowestArv', 300);
  await settle(2500);

  await expect(lowestArvField.locator('[data-part="error-message"]')).toHaveCount(0);
  await expect(page.getByTestId('form.tab.refinance.has-invalid-input')).toHaveCount(0);
  await expect(page.getByTestId('mydeals.modal.results-paused')).toHaveCount(0);
  await expect(page.getByTestId('mydeals.modal.result.cash_out_routi_conservative')).toBeVisible();
  await expect(page.getByTestId('mydeals.modal.save-status')).toHaveAttribute('data-state', 'saved');
  expect(api.matching((request) => request.method === 'POST' && request.path === '/analyze/brrr')).toHaveLength(1);
  const puts = api.matching((request) => request.method === 'PUT' && request.path === '/active-deals/{id}');
  expect(puts).toHaveLength(1);
  expect((puts[0]!.body as Record<string, unknown>).lowestArv).toBe(300);
});

test('closing on a wrong value asks first, and OK puts only that field back', async ({
  page,
  api,
  seed,
  settle,
  dialogs,
}) => {
  const deal = await seed.seedActiveDeal('BRRRR', { section: 1, lowestArv: 300 });
  await page.goto('/my-deals');
  await openActiveDeal(page, deal.id, settle);
  api.reset();

  await page.getByTestId('mydeals.modal.task').fill('Call the lender');
  await setField(page, 'lowestArv', 400);

  dialogs.setAccept(false);
  await page.getByTestId('mydeals.modal.footer-close').click();
  await expect(page.getByTestId('mydeals.modal')).toBeVisible();
  expect(api.matching((request) => request.method === 'PUT')).toHaveLength(0);

  dialogs.setAccept(true);
  await page.getByTestId('mydeals.modal.footer-close').click();
  await expect(page.getByTestId('mydeals.modal')).toHaveCount(0);
  await dialogs.expectDialogs([CLOSE_ANYWAY_DIALOG, CLOSE_ANYWAY_DIALOG]);

  const puts = api.matching((request) => request.method === 'PUT' && request.path === '/active-deals/{id}');
  expect(puts).toHaveLength(1);
  expect((puts[0]!.body as Record<string, unknown>).lowestArv).toBe(300);
  expect((puts[0]!.body as Record<string, unknown>).task).toBe('Call the lender');

  // Reopened, the field shows the saved value, not the refused one.
  await openActiveDeal(page, deal.id, settle);
  await expect(fieldInput(page, 'lowestArv')).toHaveValue('$300,000');
});

test('a bought deal pauses the same way', async ({ page, api, seed, settle }) => {
  const deal = await seed.seedBoughtDeal('BRRRR', { lowestArv: 300 });
  await page.goto('/bought-deals');
  await page.getByTestId(`boughtdeals.card.${deal.id}`).click();
  await expect(page.getByTestId('boughtdeals.modal')).toBeVisible();
  await settle(300);
  api.reset();

  await setField(page, 'lowestArv', 400);
  await settle(2500);

  await expect(page.getByTestId('form.field.lowestArv').locator('[data-part="error-message"]')).toHaveText('Lowest ARV cannot exceed ARV.');
  await expect(page.getByTestId('boughtdeals.modal.results-paused.lowestArv')).toContainText('Refinance tab');
  await expect(page.getByTestId('boughtdeals.modal.result.cash_flow')).toHaveCount(0);
  await expect(page.getByTestId('boughtdeals.modal.save-status')).toHaveText('Not saved — fix the highlighted inputs');
  expect(api.matching((request) => request.method === 'POST' || request.method === 'PUT')).toHaveLength(0);
});

test('a percentage typed past 100 is reported, not silently clamped', async ({ page, api }) => {
  await page.goto('/analyze');
  await expect(page.getByTestId('form.root')).toBeVisible();
  api.reset();

  await setField(page, 'down_payment', 150);

  await expect(fieldInput(page, 'down_payment')).toHaveValue('150%');
  await expect(page.getByTestId('form.field.down_payment').locator('[data-part="error-message"]')).toHaveText(
    'Down payment percentage must be between 0% and 100%.',
  );
  await expect(page.getByTestId('form.tab.buy.has-invalid-input')).toBeAttached();

  await setField(page, 'down_payment', 20);
  await expect(page.getByTestId('form.field.down_payment').locator('[data-part="error-message"]')).toHaveCount(0);
  await api.expectNoRequests('the Analyze page never calls the API before save');
});

test('@motion the box shakes once when its message appears, then sits still', async ({ page, seed, settle }) => {
  const deal = await seed.seedActiveDeal('BRRRR', { section: 1, lowestArv: 300 });
  await page.goto('/my-deals');
  await openActiveDeal(page, deal.id, settle);

  await setField(page, 'lowestArv', 400);
  await expect(page.getByTestId('form.field.lowestArv').locator('[data-part="error-message"]')).toBeVisible();

  const transformOfTheBox = () =>
    page.evaluate(() => {
      const box = document.querySelector('[data-testid="form.field.lowestArv"] input') as HTMLElement;
      return getComputedStyle(box).transform;
    });
  // 100 ms into a 400 ms shake the box is off its resting spot ...
  await page.clock.runFor(100);
  expect(await transformOfTheBox()).not.toBe('none');
  // ... and once it is over, the inline transform is handed back and nothing tweens.
  await page.clock.runFor(600);
  expect(await transformOfTheBox()).toBe('none');
  const liveTweens = await page.evaluate(() => window.gsap?.globalTimeline.getChildren().length ?? 0);
  expect(liveTweens).toBe(0);
});
