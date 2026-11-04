import { expect, test } from '../fixtures';
import { API_ORIGIN } from '../fixtures/env';

/**
 * A BRRRR deal's Cash Needed rows in the liquidity timeline (tasks/todo/DealCashInLiquidity.md):
 * the import preview, Done with Undo on an overdue row, the postpone chips, an amount edit, an
 * overdue money-in row given a new date, a bulk postpone and a milestone moved with its list of
 * affected rows. The browser clock is frozen on 2026-09-04 (fixtures/clock.ts).
 */

const SEED_HEADERS = { 'x-e2e-seed': '1' };
const TRANSITION_MS = 400;
/** The purchase closes after "today", so nothing of the deal is overdue yet. */
const DEAL_DATES_AFTER_TODAY = { contractDate: '2026-08-28', buyClosingDate: '2026-09-10', address: '7 Preview Lane', section: 1 };

type Request = import('@playwright/test').APIRequestContext;
type Page = import('@playwright/test').Page;

/** The overdue rows live in the overdue chip's popover on the theater page. */
async function openOverdueRows(page: Page): Promise<void> {
  await page.getByTestId('theater.figure.overdue').click();
  await expect(page.getByTestId('theater.overdue-popover')).toBeVisible();
}

async function seedSettings(request: Request): Promise<void> {
  const response = await request.put(`${API_ORIGIN}/liquidity/settings`, {
    headers: SEED_HEADERS,
    data: { opening_balance_dollars: 150000, opening_balance_date: '2026-09-04', reserve_dollars: 5000 },
  });
  expect(response.ok()).toBe(true);
}

async function seedTransaction(request: Request, effective_date: string, amount_dollars: number, description: string): Promise<string> {
  const response = await request.post(`${API_ORIGIN}/liquidity/transactions`, {
    headers: SEED_HEADERS,
    data: { effective_date, amount_dollars, description },
  });
  expect(response.ok()).toBe(true);
  return ((await response.json()) as { id: string }).id;
}

test('a deal is imported only after its preview, from the My Deals modal', async ({ page, api, seed, request, settle }) => {
  await seedSettings(request);
  const deal = await seed.seedActiveDeal('BRRRR', DEAL_DATES_AFTER_TODAY);

  await page.goto('/my-deals');
  await page.getByTestId(`mydeals.card.${deal.id}`).click();
  await expect(page.getByTestId('mydeals.modal')).toBeVisible();
  await expect(page.getByTestId('import-to-liquidity')).toHaveText(/Import to liquidity/);

  api.reset();
  await page.getByTestId('import-to-liquidity').click();
  const preview = page.getByTestId('deal-import-preview');
  await expect(preview).toBeVisible();
  // The full-screen decision view: the verdict first, the chart of both lines, the insights.
  const viewportWidth = page.viewportSize()!.width;
  expect((await preview.boundingBox())!.width).toBeGreaterThan(viewportWidth - 2);
  await expect(preview.getByTestId('deal-impact.verdict')).toHaveAttribute('data-risk-level', 'stays_above_reserve');
  await expect(preview.getByTestId('deal-impact.verdict.headline')).toContainText('You stay above your $5,000 reserve');
  await expect(preview.locator('[data-part="before-line"]')).toHaveCount(1);
  await expect(preview.locator('[data-part="after-line"]')).toHaveCount(1);
  await expect(preview.locator('[data-part="key-date-flag"][data-key-date="purchase_closed"]')).toHaveCount(1);
  await expect(preview.getByTestId('deal-import-preview.insights')).toContainText('Lowest balance');
  await expect(preview.getByTestId('deal-import-preview.insights')).toContainText('Largest single-day outflow');
  // The rows are on demand for an import.
  await expect(preview.locator('[data-testid="deal-cash-row-change"]')).toHaveCount(0);
  await preview.getByTestId('deal-impact.rows.toggle').click();
  await expect(preview.locator('[data-testid="deal-cash-row-change"][data-change-kind="added"]').first()).toBeVisible();

  const confirm = preview.getByTestId('deal-import-preview.confirm');
  await (await confirm.isVisible() ? confirm : preview.getByTestId('deal-import-preview.confirm-phone')).click();
  await settle(TRANSITION_MS);
  await expect(preview).toHaveCount(0);
  await expect(page.getByTestId('import-to-liquidity')).toHaveText(/Re-sync liquidity/);
  await api.expectContract('liquidity-deal-import');

  await page.goto('/liquidity');
  const legendToggle = page.getByTestId('theater.legend-toggle');
  await expect(legendToggle).toBeVisible();
  if ((await legendToggle.getAttribute('aria-expanded')) !== 'true') await legendToggle.click();
  await settle(TRANSITION_MS);
  await expect(page.getByTestId('theater.legend.deal')).toContainText('7 Preview Lane');
});

test('an overdue payment counts on today until it is marked done, and Done can be undone', async ({ page, request }) => {
  await seedSettings(request);
  const overdueId = await seedTransaction(request, '2026-09-01', -1970.83, 'HML interest for August 2026');

  await page.goto('/liquidity');
  await expect(page.getByTestId('theater.figure.overdue')).toContainText('1 overdue');
  await openOverdueRows(page);
  await expect(page.getByTestId('overdue.count')).toContainText('1 overdue');
  await page.getByTestId(`rowactions.${overdueId}.done`).click();
  await expect(page.getByTestId('liquidity.toast')).toContainText('Marked done.');
  await expect(page.getByTestId('overdue.root')).toHaveCount(0);

  await page.getByTestId('liquidity.toast.undo').click();
  await expect(page.getByTestId('overdue.count')).toContainText('1 overdue');
});

test('a postpone chip, an amount edit and a new date for overdue money in', async ({ page, request }) => {
  await seedSettings(request);
  const paymentId = await seedTransaction(request, '2026-09-01', -450, 'HOA dues');
  const rentId = await seedTransaction(request, '2026-09-01', 2600, 'Rent collected');

  await page.goto('/liquidity');
  await openOverdueRows(page);
  await expect(page.getByTestId(`overdue.row.${rentId}`)).toContainText('not counted until you give it a new date');

  await page.getByTestId(`amount.${paymentId}`).click();
  await page.getByTestId(`amount.${paymentId}.input`).fill('500');
  await page.getByTestId(`amount.${paymentId}.input`).press('Enter');
  await expect(page.getByTestId(`amount.${paymentId}`)).toContainText('500');

  await page.getByTestId(`rowactions.${rentId}.postpone.week`).click();
  await expect(page.getByTestId(`overdue.row.${rentId}`)).toHaveCount(0);
  await page.getByTestId(`rowactions.${paymentId}.postpone.day`).click();
  await expect(page.getByTestId('overdue.root')).toHaveCount(0);
});

test('a bulk postpone moves every selected overdue row', async ({ page, request }) => {
  await seedSettings(request);
  const firstId = await seedTransaction(request, '2026-08-15', -300, 'Utilities');
  const secondId = await seedTransaction(request, '2026-09-01', -450, 'HOA dues');

  await page.goto('/liquidity');
  await expect(page.getByTestId('theater.figure.overdue')).toContainText('2 overdue');
  await openOverdueRows(page);
  await expect(page.getByTestId('overdue.count')).toContainText('2 overdue');
  await page.getByTestId(`overdue.row.${firstId}.select`).check();
  await page.getByTestId(`overdue.row.${secondId}.select`).check();
  await page.getByTestId('overdue.bulk.postpone.week').click();
  await expect(page.getByTestId('overdue.root')).toHaveCount(0);
});

test('moving the purchase closing lists the affected rows first, then writes the deal', async ({ page, api, seed, request, settle }) => {
  await seedSettings(request);
  const deal = await seed.seedActiveDeal('BRRRR', DEAL_DATES_AFTER_TODAY);
  const imported = await request.post(`${API_ORIGIN}/liquidity/deals/my_deals/${deal.id}/import`, {
    headers: SEED_HEADERS,
    data: { today: '2026-09-04' },
  });
  expect(imported.ok()).toBe(true);

  await page.goto('/liquidity');
  await page.getByTestId('theater.sheet.toggle').click();
  await settle(TRANSITION_MS);
  const purchaseClosed = page.locator('[data-testid="theater.sheet.milestone"][data-milestone="purchase_closed"]');
  await expect(purchaseClosed).toContainText('Sep 10, 2026');

  api.reset();
  await purchaseClosed.getByTestId('theater.sheet.milestone.move').click();
  const modal = page.getByTestId('deal-milestone-change');
  await expect(modal).toBeVisible();
  await modal.getByTestId('deal-milestone-change.date').fill('2026-09-14');
  await expect(modal.getByTestId('deal-milestone-change.milestones')).toContainText('Refi closed');
  await expect(modal.locator('[data-testid="deal-cash-row-change"][data-change-kind="updated"]').first()).toBeVisible();

  await modal.getByTestId('deal-milestone-change.confirm').click();
  await settle(TRANSITION_MS);
  await expect(modal).toHaveCount(0);
  await expect(page.getByTestId('liquidity.toast')).toContainText('Milestone saved');
  await expect(purchaseClosed).toContainText('Sep 14, 2026');
  await api.expectContract('liquidity-deal-milestone-move');
});
