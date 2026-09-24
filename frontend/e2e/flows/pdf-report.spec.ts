import type { Page } from '@playwright/test';

import { BRRRR_PAYLOAD, expect, test } from '../fixtures';

/**
 * The branded deal report.
 *
 * "Generate Report" first opens a picker of the modal's result tiles, all
 * checked; Generate fetches the PDF as a blob, previews it inside the app, and
 * only downloads it if the user asks. Frozen here: the picker's default, the
 * request that produces the PDF (with the picked results), that the response
 * really is a PDF, and the file name the browser is offered.
 */

const BRRRR_RESULT_KEYS_IN_TILE_ORDER = [
  'cash_flow', 'cash_out', 'cash_out_routi', 'cash_on_cash', 'dscr', 'equity', 'roi', 'net_profit',
  'total_cash_needed_for_deal', 'cash_to_close_buy', 'cash_out_routi_conservative', 'stolen_money',
];

/** Press "Generate Report", check the picker opened with every result checked, uncheck some, press Generate. */
async function generateReport(page: Page, testIdPrefix: 'mydeals' | 'boughtdeals', uncheckedResultKeys: string[] = []) {
  const button = page.getByTestId(`${testIdPrefix}.modal.view-report`);
  await expect(button).toContainText('Generate Report');
  await button.click();
  const picker = page.getByTestId('generate-report-result-picker');
  await expect(picker).toBeVisible();
  const options = picker.locator('[data-part="result-option"]');
  await expect(options).toHaveCount(BRRRR_RESULT_KEYS_IN_TILE_ORDER.length);
  expect(await options.evaluateAll((els) => els.map((el) => (el as HTMLElement).dataset.resultKey))).toEqual(
    BRRRR_RESULT_KEYS_IN_TILE_ORDER,
  );
  await expect(picker.locator('[data-part="result-option-input"]:checked')).toHaveCount(BRRRR_RESULT_KEYS_IN_TILE_ORDER.length);
  for (const resultKey of uncheckedResultKeys) {
    await picker.locator(`[data-result-key="${resultKey}"] input`).uncheck();
  }
  await picker.locator('[data-part="generate"]').click();
  await expect(picker).toBeHidden();
}

const EXPECTED_FILENAME = `BigWhales_BRRRR_${BRRRR_PAYLOAD.address.replace(
  /[^A-Za-z0-9]+/g,
  '_',
)}.pdf`;

test('generating a report with every result fetches a PDF blob and previews it', async ({
  page,
  api,
  seed,
}) => {
  const deal = await seed.seedActiveDeal('BRRRR', { section: 1 });

  await page.goto('/my-deals');
  await page.getByTestId(`mydeals.card.${deal.id}`).click();
  await expect(page.getByTestId('mydeals.modal')).toBeVisible();

  api.reset();

  await generateReport(page, 'mydeals');

  const preview = page.getByTestId('mydeals.pdf-modal');
  await expect(preview).toBeVisible();
  await expect(page.getByTestId('mydeals.pdf-modal.iframe')).toHaveAttribute(
    'src',
    /^blob:/,
  );

  await api.expectContract('pdf-report');
});

test('the download button offers the branded filename', async ({ page, seed }) => {
  const deal = await seed.seedActiveDeal('BRRRR', { section: 1 });

  await page.goto('/my-deals');
  await page.getByTestId(`mydeals.card.${deal.id}`).click();
  await generateReport(page, 'mydeals');
  await expect(page.getByTestId('mydeals.pdf-modal')).toBeVisible();

  const [download] = await Promise.all([
    page.waitForEvent('download'),
    page.getByTestId('mydeals.pdf-modal.download').click(),
  ]);

  expect(download.suggestedFilename()).toBe(EXPECTED_FILENAME);
});

test('a bought deal offers the same report from its modal', async ({ page, api, seed }) => {
  const bought = await seed.seedBoughtDeal('BRRRR');

  await page.goto('/bought-deals');
  await page.getByTestId(`boughtdeals.card.${bought.id}`).click();
  await expect(page.getByTestId('boughtdeals.modal')).toBeVisible();

  api.reset();

  await generateReport(page, 'boughtdeals');

  await expect(page.getByTestId('boughtdeals.pdf-modal')).toBeVisible();
  await expect(page.getByTestId('boughtdeals.pdf-modal.iframe')).toHaveAttribute(
    'src',
    /^blob:/,
  );

  await api.expectContract('pdf-report-bought');
});

test('unchecked results are left out of the report request', async ({ page, api, seed }) => {
  const deal = await seed.seedActiveDeal('BRRRR', { section: 1 });

  await page.goto('/my-deals');
  await page.getByTestId(`mydeals.card.${deal.id}`).click();
  await expect(page.getByTestId('mydeals.modal')).toBeVisible();

  api.reset();

  await generateReport(page, 'mydeals', ['cash_out', 'stolen_money']);

  await expect(page.getByTestId('mydeals.pdf-modal.iframe')).toHaveAttribute('src', /^blob:/);
  await api.expectContract('pdf-report-selected-results');
});
