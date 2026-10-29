import { readFileSync } from 'node:fs';
import type { Page } from '@playwright/test';

import { BRRRR_PAYLOAD, expect, test } from '../fixtures';

/**
 * The interactive deal report.
 *
 * "Generate Report" first opens a picker of the modal's result tiles, all checked;
 * Generate fetches the report (one self-contained HTML file that works like the
 * breakdown popups) as a blob and previews it in a sandboxed frame inside the app,
 * where its rows expand in place. Download offers the `.html` file. Frozen here: the
 * picker's default, the request (with the picked results and the deal-inputs choice), the
 * in-app drill-down and the collapsed Deal Inputs section, the
 * file name, and that the downloaded file works on its own with JavaScript OFF, as it
 * does in the iPhone preview a WhatsApp or Mail attachment opens in.
 */

const BRRRR_RESULT_KEYS_IN_TILE_ORDER = [
  'cash_flow', 'cash_out', 'cash_out_routi', 'cash_on_cash', 'dscr', 'equity', 'roi', 'net_profit',
  'total_cash_needed_for_deal', 'cash_to_close_buy', 'cash_out_routi_conservative', 'stolen_money',
];

/**
 * Press "Generate Report", check the picker opened with every result and "Include deal inputs" checked,
 * uncheck what the test asks, press Generate.
 */
async function generateReport(
  page: Page,
  testIdPrefix: 'mydeals' | 'boughtdeals',
  uncheckedResultKeys: string[] = [],
  includeDealInputs = true,
) {
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
  const includeDealInputsBox = picker.locator('[data-part="include-deal-inputs-input"]');
  await expect(includeDealInputsBox).toBeChecked();
  if (!includeDealInputs) await includeDealInputsBox.uncheck();
  await picker.locator('[data-part="generate"]').click();
  await expect(picker).toBeHidden();
}

const EXPECTED_FILENAME = `BigWhales_BRRRR_${BRRRR_PAYLOAD.address.replace(
  /[^A-Za-z0-9]+/g,
  '_',
)}.html`;

async function openSeededDealAndGenerate(page: Page, seed: { seedActiveDeal: (t: 'BRRRR', o: { section: number }) => Promise<{ id: string }> }) {
  const deal = await seed.seedActiveDeal('BRRRR', { section: 1 });
  await page.goto('/my-deals');
  await page.getByTestId(`mydeals.card.${deal.id}`).click();
  await expect(page.getByTestId('mydeals.modal')).toBeVisible();
}

test('generating a report with every result previews the interactive report, whose rows expand in place', async ({
  page,
  api,
  seed,
}) => {
  await openSeededDealAndGenerate(page, seed);
  api.reset();

  await generateReport(page, 'mydeals');

  await expect(page.getByTestId('mydeals.report-modal')).toBeVisible();
  const iframe = page.getByTestId('mydeals.report-modal.iframe');
  await expect(iframe).toHaveAttribute('src', /^blob:/);
  await expect(iframe).toHaveAttribute('sandbox', '');
  await api.expectContract('deal-report');

  const report = page.frameLocator('[data-testid="mydeals.report-modal.iframe"]');
  await expect(report.locator('h2').first()).toHaveText('How Cash Flow is calculated');
  await expect(report.locator('#result-0 .headline')).toHaveText('$97.04'); // a regular year's tax is the bill × 0.96 ÷ 12
  // A second-level row starts closed, as in the popup; a tap opens it in place, another closes it.
  // The row's own <details>: the parent of the summary whose label is Operating Expenses.
  const operatingExpenses = report.locator('#result-0 summary', { has: report.locator('.label', { hasText: /^Operating Expenses$/ }) }).first().locator('..');
  await expect(operatingExpenses).not.toHaveAttribute('open', '');
  await operatingExpenses.locator('> summary').click();
  await expect(operatingExpenses).toHaveAttribute('open', '');
  await expect(operatingExpenses.locator('> .children')).toContainText('Management 8% of rent');
  await operatingExpenses.locator('> summary').click();
  await expect(operatingExpenses).not.toHaveAttribute('open', '');

  // The Deal Inputs section: collapsed; a tap opens the four stages with the deal's values.
  const dealInputs = report.locator('details#deal-inputs');
  await expect(dealInputs).not.toHaveAttribute('open', '');
  await dealInputs.locator('> summary').click();
  await expect(dealInputs).toHaveAttribute('open', '');
  await expect(dealInputs.locator('.stage-title')).toHaveText(['Buy', 'Rehab', 'Rent & Holding', 'Refinance']);
  const purchasePrice = dealInputs.locator('.input-row', { has: report.locator('dt', { hasText: /^Purchase Price$/ }) });
  await expect(purchasePrice.locator('.input-value')).toHaveText(`$${(BRRRR_PAYLOAD.purchasePrice * 1000).toLocaleString('en-US')}`);
});

test('the download is the .html file, and it works on its own with JavaScript off (the iPhone preview)', async ({
  page,
  seed,
  browser,
}) => {
  await openSeededDealAndGenerate(page, seed);
  await generateReport(page, 'mydeals');
  await expect(page.getByTestId('mydeals.report-modal')).toBeVisible();

  const [download] = await Promise.all([
    page.waitForEvent('download'),
    page.getByTestId('mydeals.report-modal.download').click(),
  ]);
  expect(download.suggestedFilename()).toBe(EXPECTED_FILENAME);
  const html = readFileSync((await download.path())!, 'utf8');
  expect(html.startsWith('<!doctype html>')).toBe(true);
  expect(html).not.toMatch(/https?:\/\//);

  // Open the file the way a phone's attachment preview does: no network, no JavaScript.
  const offline = await browser.newContext({ javaScriptEnabled: false, viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });
  try {
    const phone = await offline.newPage();
    const blockedRequests: string[] = [];
    await phone.route('**/*', (route) => {
      blockedRequests.push(route.request().url());
      return route.abort();
    });
    await phone.setContent(html);
    expect(blockedRequests).toEqual([]);
    await expect(phone.locator('h2').first()).toHaveText('How Cash Flow is calculated');
    // The extras that need a script stay hidden; the drill-down itself does not need one.
    await expect(phone.locator('.page-tools')).toBeHidden();
    const operatingExpenses = phone.locator('#result-0 summary', { has: phone.locator('.label', { hasText: /^Operating Expenses$/ }) }).first().locator('..');
    await expect(operatingExpenses).not.toHaveAttribute('open', '');
    await operatingExpenses.locator('> summary').tap();
    await expect(operatingExpenses).toHaveAttribute('open', '');
    // The Deal Inputs section opens natively too, and its stages fit the phone.
    await phone.locator('details#deal-inputs > summary').tap();
    await expect(phone.locator('details#deal-inputs')).toHaveAttribute('open', '');
    await expect(phone.locator('#inputs-refinance .stage-title')).toHaveText('Refinance');
    // The result tiles jump to their card.
    await phone.locator('a.tile[href="#result-8"]').tap();
    await expect(phone.locator('#result-8')).toBeInViewport();
    // Phone width: nothing scrolls sideways.
    expect(await phone.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)).toBeLessThanOrEqual(0);
  } finally {
    await offline.close();
  }
});

test('a bought deal offers the same report from its modal', async ({ page, api, seed }) => {
  const bought = await seed.seedBoughtDeal('BRRRR');

  await page.goto('/bought-deals');
  await page.getByTestId(`boughtdeals.card.${bought.id}`).click();
  await expect(page.getByTestId('boughtdeals.modal')).toBeVisible();

  api.reset();

  await generateReport(page, 'boughtdeals');

  await expect(page.getByTestId('boughtdeals.report-modal')).toBeVisible();
  await expect(page.getByTestId('boughtdeals.report-modal.iframe')).toHaveAttribute('src', /^blob:/);
  await expect(page.frameLocator('[data-testid="boughtdeals.report-modal.iframe"]').locator('h2').first()).toHaveText(
    'How Cash Flow is calculated',
  );

  await api.expectContract('deal-report-bought');
});

test('unchecked results and unchecked deal inputs are left out of the report request and the report', async ({ page, api, seed }) => {
  await openSeededDealAndGenerate(page, seed);
  api.reset();

  await generateReport(page, 'mydeals', ['cash_out', 'stolen_money'], false);

  await expect(page.getByTestId('mydeals.report-modal.iframe')).toHaveAttribute('src', /^blob:/);
  const report = page.frameLocator('[data-testid="mydeals.report-modal.iframe"]');
  await expect(report.locator('section.card')).toHaveCount(10);
  await expect(report.locator('h2', { hasText: 'How Cash Out is calculated' })).toHaveCount(0);
  // "Include deal inputs" unchecked: no inputs section, and the request does not ask for one.
  await expect(report.locator('details#deal-inputs')).toHaveCount(0);
  await api.expectContract('deal-report-selected-results');
});
