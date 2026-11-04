import AxeBuilder from '@axe-core/playwright';

import { expect, test } from '../fixtures';
import { API_ORIGIN } from '../fixtures/env';

/**
 * The liquidity page, which is the theater (tasks/todo/LiquidityTheaterMode.md, tasks/todo/LiquidityTheaterOnly.md):
 * the chart over the whole viewport; Esc and × leave to the previous page, or the Dashboard for a direct link; the
 * legend with a deal's overdue rows, its open rows by month and "Remove from timeline"; the deals sheet with a
 * one-tap Done and "Done on another date"; the hover preview and the day modal. The browser clock is frozen on
 * 2026-09-04 (fixtures/clock.ts).
 */

const SEED_HEADERS = { 'x-e2e-seed': '1' };
const TRANSITION_MS = 400;
const TODAY = '2026-09-04';
/** Contract and purchase closing before "today": the deal has overdue rows and overdue milestones. */
const DEAL_WITH_OVERDUE_ROWS = { contractDate: '2026-08-20', buyClosingDate: '2026-08-28', address: '12 Theater Way, Jacksonville, FL 32207', section: 1 };

type Request = import('@playwright/test').APIRequestContext;
type Page = import('@playwright/test').Page;

async function seedSettings(request: Request): Promise<void> {
  const response = await request.put(`${API_ORIGIN}/liquidity/settings`, {
    headers: SEED_HEADERS,
    data: { opening_balance_dollars: 150000, opening_balance_date: TODAY, reserve_dollars: 5000 },
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

async function importDeal(request: Request, dealId: string): Promise<void> {
  const response = await request.post(`${API_ORIGIN}/liquidity/deals/my_deals/${dealId}/import`, {
    headers: SEED_HEADERS,
    data: { today: TODAY },
  });
  expect(response.ok()).toBe(true);
}

async function openLegend(page: Page, settle: (ms: number) => Promise<void>) {
  const legend = page.getByTestId('theater.legend');
  // Open by default on a wide screen, closed on a phone.
  const legendToggle = page.getByTestId('theater.legend-toggle');
  await expect(legendToggle).toBeVisible();
  if ((await legendToggle.getAttribute('aria-expanded')) !== 'true') await legendToggle.click();
  await settle(TRANSITION_MS);
  await expect(legend).toBeVisible();
  return legend;
}

test('/liquidity is the theater over the whole viewport; Esc and × leave to the previous page or the Dashboard', async ({ page, request, settle }) => {
  await seedSettings(request);
  await seedTransaction(request, '2026-09-10', -1200, 'Plumber');

  // In-app navigation: Esc goes back to where you came from.
  await page.goto('/my-deals');
  await expect(page.getByTestId('mydeals.add-deal')).toBeVisible();
  await page.locator('a[href="/liquidity"]:visible').first().click();
  const theater = page.getByTestId('theater.root');
  await expect(theater).toBeVisible();
  await expect(page).toHaveURL(/\/liquidity$/);

  // The chart spans the viewport's width: no app sidebar, no Upcoming rail beside it.
  const viewportWidth = page.viewportSize()!.width;
  const chartBox = (await theater.getByTestId('chart.container').boundingBox())!;
  expect(chartBox.width).toBeGreaterThan(viewportWidth - 2);
  await expect(theater.locator('[data-part="today-pill"]')).toHaveCount(1);

  await page.keyboard.press('Escape');
  await settle(TRANSITION_MS);
  await expect(page).toHaveURL(/\/my-deals$/);
  await expect(theater).toHaveCount(0);

  // A direct link (an old ?view=theater one still works) has no in-app page to go back to: × goes to the Dashboard.
  await page.goto('/liquidity?view=theater');
  await expect(theater).toBeVisible();
  await theater.getByTestId('theater.close').click();
  await settle(TRANSITION_MS);
  await expect(page).toHaveURL(/\/$/);
  await expect(theater).toHaveCount(0);
});

test('the legend lists a deal with its overdue rows; Done clears one, and the deal can leave the timeline', async ({ page, seed, request, dialogs, settle }) => {
  await seedSettings(request);
  const deal = await seed.seedActiveDeal('BRRRR', DEAL_WITH_OVERDUE_ROWS);
  await importDeal(request, deal.id);

  await page.goto('/liquidity');
  const legend = await openLegend(page, settle);
  const dealEntry = legend.getByTestId('theater.legend.deal');
  await expect(dealEntry).toContainText('12 Theater Way');
  const overduePill = dealEntry.getByTestId('theater.legend.deal.overdue');
  await expect(overduePill).toContainText(/\d+ overdue/);
  const overdueCountBefore = Number((await overduePill.innerText()).split(' ')[0]);

  await dealEntry.getByTestId('theater.legend.deal.toggle').click();
  await expect(dealEntry.getByTestId('theater.legend.deal.toggle')).toHaveAttribute('aria-expanded', 'true');
  const drawer = dealEntry.getByTestId('theater.legend.deal.drawer');
  const firstOverdueRow = drawer.locator('[data-testid^="theater.legend.overdue-row."]').first();
  await expect(firstOverdueRow).toBeVisible();
  await firstOverdueRow.locator('[data-testid$=".done"]').click();
  await expect(page.getByTestId('liquidity.toast')).toContainText('Marked done.');
  if (overdueCountBefore > 1) await expect(overduePill).toContainText(`${overdueCountBefore - 1} overdue`);

  await dealEntry.getByTestId('theater.legend.deal.remove').click();
  await expect.poll(() => dialogs.messages.length).toBe(2);
  expect(dialogs.messages[0]).toContain('Remove the');
  await settle(TRANSITION_MS);
  await expect(page.getByTestId('liquidity.toast')).toContainText(/Removed \d+ rows, earnest money refund added/);
  await expect(legend.getByTestId('theater.legend.deal')).toHaveCount(0);
});

test('the deals sheet approves a milestone in one tap when nothing else changes', async ({ page, seed, request, settle }) => {
  await seedSettings(request);
  const deal = await seed.seedActiveDeal('BRRRR', DEAL_WITH_OVERDUE_ROWS);
  await importDeal(request, deal.id);

  await page.goto('/liquidity');
  await page.getByTestId('theater.sheet.toggle').click();
  const sheet = page.getByTestId('theater.sheet');
  await expect(sheet.getByTestId('theater.sheet.deal')).toContainText('12 Theater Way');

  const contractSigned = sheet.locator('[data-testid="theater.sheet.milestone"][data-milestone="contract_signed"]');
  await expect(contractSigned).toHaveAttribute('data-done', 'false');
  await contractSigned.getByTestId('theater.sheet.milestone.done').click();
  const reviewModal = page.getByTestId('deal-milestone-change');
  // Either it was applied at once, or (rows would change) its before -> after list opened: confirm it there.
  await expect(contractSigned.and(page.locator('[data-done="true"]')).or(reviewModal)).toBeVisible();
  if (await reviewModal.isVisible()) {
    await reviewModal.getByTestId('deal-milestone-change.confirm').click();
    await settle(TRANSITION_MS);
  }
  await expect(contractSigned).toHaveAttribute('data-done', 'true');
  await expect(contractSigned.getByTestId('theater.sheet.milestone.done')).toHaveCount(0);
});

test('a milestone can be marked done on another date, from the deals sheet', async ({ page, seed, request, settle }) => {
  await seedSettings(request);
  const deal = await seed.seedActiveDeal('BRRRR', DEAL_WITH_OVERDUE_ROWS);
  await importDeal(request, deal.id);

  await page.goto('/liquidity');
  await page.getByTestId('theater.sheet.toggle').click();
  await settle(TRANSITION_MS);
  const contractSigned = page.locator('[data-testid="theater.sheet.milestone"][data-milestone="contract_signed"]');
  await contractSigned.getByTestId('theater.sheet.milestone.done-on-date').click();
  const modal = page.getByTestId('deal-milestone-change');
  await expect(modal).toContainText('Approve: Contract signed');
  await modal.getByTestId('deal-milestone-change.date').fill('2026-08-21');
  await expect(modal.getByTestId('deal-milestone-change.confirm')).toBeEnabled();
  await modal.getByTestId('deal-milestone-change.confirm').click();
  await settle(TRANSITION_MS);
  await expect(modal).toHaveCount(0);
  await expect(contractSigned).toHaveAttribute('data-done', 'true');
  await expect(contractSigned).toContainText('Aug 21, 2026');
});

test("the legend lists a deal's key dates and transactions by month, and a row opens its day", async ({ page, seed, request, settle }) => {
  await seedSettings(request);
  const deal = await seed.seedActiveDeal('BRRRR', DEAL_WITH_OVERDUE_ROWS);
  await importDeal(request, deal.id);

  await page.goto('/liquidity');
  const legend = await openLegend(page, settle);
  await legend.getByTestId('theater.legend.deal.toggle').click();
  await legend.getByTestId('theater.legend.deal.transactions-section').click();
  // "Today" is Sep 4: September opens first; August holds the contract, the EMD and the closing.
  const august = legend.locator('[data-testid="theater.legend.transactions-month"][data-month="2026-08"]');
  await august.getByTestId('theater.legend.transactions-month.toggle').click();
  await expect(august.locator('[data-testid="theater.legend.key-date"][data-key-date="contract_signed"]')).toContainText('Contract signed');
  await expect(august.locator('[data-testid="theater.legend.key-date"][data-key-date="purchase_closed"]')).toContainText('overdue');
  const firstRow = august.locator('[data-testid^="theater.legend.transaction."][data-done="false"]').first();
  await expect(firstRow).toContainText('Aug 20');
  await firstRow.click();
  const dayModal = page.getByTestId('theater.day-modal');
  await expect(dayModal).toBeVisible();
  await expect(dayModal).toContainText('August 20, 2026');
});

test('a row marked Done by mistake is struck through in the legend and in its day, and Undo reopens it', async ({ page, seed, request, settle }) => {
  await seedSettings(request);
  const deal = await seed.seedActiveDeal('BRRRR', DEAL_WITH_OVERDUE_ROWS);
  await importDeal(request, deal.id);

  await page.goto('/liquidity');
  const legend = await openLegend(page, settle);
  const dealEntry = legend.getByTestId('theater.legend.deal');
  const overduePill = dealEntry.getByTestId('theater.legend.deal.overdue');
  const overdueCountBefore = Number((await overduePill.innerText()).split(' ')[0]);
  await dealEntry.getByTestId('theater.legend.deal.toggle').click();
  const overdueRow = dealEntry.locator('[data-testid^="theater.legend.overdue-row."]').first();
  const rowId = (await overdueRow.getAttribute('data-testid'))!.replace('theater.legend.overdue-row.', '');
  await overdueRow.locator(`[data-testid="rowactions.${rowId}.done"]`).click();
  await expect(page.getByTestId('liquidity.toast')).toContainText('Marked done.');
  // The toast and its Undo go away.
  await settle(5000);
  await expect(page.getByTestId('liquidity.toast')).toHaveCount(0);
  await expect(overduePill).toContainText(`${overdueCountBefore - 1} overdue`);

  await dealEntry.getByTestId('theater.legend.deal.transactions-section').click();
  await dealEntry.locator('[data-testid="theater.legend.transactions-month"][data-month="2026-08"]').getByTestId('theater.legend.transactions-month.toggle').click();
  const doneRow = dealEntry.getByTestId(`theater.legend.transaction.${rowId}`);
  await expect(doneRow).toHaveAttribute('data-done', 'true');
  await doneRow.getByTestId(`theater.legend.transaction.${rowId}.undo`).click();
  await expect(page.getByTestId('liquidity.toast')).toContainText('Reopened.');
  await expect(overduePill).toContainText(`${overdueCountBefore} overdue`);
  await expect(dealEntry.getByTestId(`theater.legend.overdue-row.${rowId}`)).toBeVisible();

  // Done again, then undone from its day.
  await dealEntry.locator(`[data-testid="rowactions.${rowId}.done"]`).click();
  await settle(5000);
  await expect(dealEntry.getByTestId(`theater.legend.transaction.${rowId}`)).toHaveAttribute('data-done', 'true');
  const doneRowDate = (await doneRow.locator('span').first().innerText()).trim();
  expect(doneRowDate).toBe('Aug 20');   // the EMD, the earliest overdue row, on the contract day
  await dealEntry.locator('[data-testid="theater.legend.key-date"][data-key-date="contract_signed"]').click();
  const dayModal = page.getByTestId('theater.day-modal');
  await expect(dayModal).toBeVisible();
  // The contract day is Aug 20, the EMD's day: the done row shows struck through there.
  const doneInDay = dayModal.getByTestId(`theater.day-modal.done-row.${rowId}`);
  await expect(doneInDay).toBeVisible();
  await doneInDay.getByTestId(`theater.day-modal.done-row.${rowId}.undo`).click();
  await expect(page.getByTestId('liquidity.toast')).toContainText('Reopened.');
  await expect(doneInDay).toHaveCount(0);
});

test('hovering a day previews it; a click opens the day in full, with every action', async ({ page, request, settle }, testInfo) => {
  test.skip(testInfo.project.name.startsWith('Mobile'), 'hover is a desktop pointer gesture');
  await seedSettings(request);
  const plumberId = await seedTransaction(request, TODAY, -1200, 'Plumber');

  await page.goto('/liquidity');
  const theater = page.getByTestId('theater.root');
  const chart = theater.getByTestId('chart.container');
  await expect(chart).toBeVisible();
  // Today's column, wherever the chart scrolled it.
  const chartBox = (await chart.boundingBox())!;
  const todayColumn = (await chart.locator(`[data-date="${TODAY}"] [data-part="today-pill"] rect`).boundingBox())!;
  const box = { x: todayColumn.x + todayColumn.width / 2, y: chartBox.y + chartBox.height / 2 };
  await page.mouse.move(box.x, box.y);
  const tooltip = theater.getByTestId('chart.tooltip');
  await expect(tooltip).toHaveAttribute('data-floating', 'true');
  await expect(tooltip).toContainText('Plumber');

  await page.mouse.click(box.x, box.y);
  const dayModal = theater.getByTestId('theater.day-modal');
  await expect(dayModal).toBeVisible();
  await expect(dayModal).toContainText('Friday, September 4, 2026');
  await expect(dayModal.getByTestId('theater.day-modal.money-out')).toContainText('1,200');
  await dayModal.getByTestId(`rowactions.${plumberId}.postpone.day`).click();
  await expect(page.getByTestId('liquidity.toast')).toContainText('Moved to 2026-09-05.');
  await expect(dayModal.getByTestId(`daydetail.txn.${plumberId}`)).toHaveCount(0);

  await dayModal.getByTestId('theater.day-modal.next').click();
  await expect(dayModal.getByTestId(`daydetail.txn.${plumberId}`)).toBeVisible();

  // Esc closes the modal first, then the theater.
  await page.keyboard.press('Escape');
  await settle(TRANSITION_MS);
  await expect(dayModal).toHaveCount(0);
  await expect(theater).toBeVisible();
});

test('the deal impact view has no serious accessibility violations', async ({ page, seed, request }, testInfo) => {
  test.skip(testInfo.project.name !== 'chromium', 'axe runs on chromium only');
  await seedSettings(request);
  const deal = await seed.seedActiveDeal('BRRRR', DEAL_WITH_OVERDUE_ROWS);
  await page.goto('/my-deals');
  await page.getByTestId(`mydeals.card.${deal.id}`).click();
  await page.getByTestId('import-to-liquidity').click();
  await expect(page.getByTestId('deal-impact.verdict')).toBeVisible();
  await page.getByTestId('deal-impact.rows.toggle').click();
  await page.clock.resume();
  const results = await new AxeBuilder({ page }).include('[data-testid="deal-import-preview"]').analyze();
  const seriousViolations = results.violations.filter((violation) => violation.impact === 'serious' || violation.impact === 'critical');
  expect(seriousViolations.map((violation) => `${violation.id}: ${violation.nodes.map((node) => node.target.join(' ')).join(', ')}`)).toEqual([]);
});

test('theater mode has no serious accessibility violations', async ({ page, seed, request, settle }, testInfo) => {
  test.skip(testInfo.project.name !== 'chromium', 'axe runs on chromium only');
  await seedSettings(request);
  const deal = await seed.seedActiveDeal('BRRRR', DEAL_WITH_OVERDUE_ROWS);
  await importDeal(request, deal.id);

  await page.goto('/liquidity');
  await openLegend(page, settle);
  await page.getByTestId('theater.sheet.toggle').click();
  // axe schedules its work on timers: let the frozen clock run.
  await page.clock.resume();
  const results = await new AxeBuilder({ page }).include('[data-testid="theater.root"]').analyze();
  const seriousViolations = results.violations.filter((violation) => violation.impact === 'serious' || violation.impact === 'critical');
  expect(seriousViolations.map((violation) => `${violation.id}: ${violation.nodes.map((node) => node.target.join(' ')).join(', ')}`)).toEqual([]);
});
