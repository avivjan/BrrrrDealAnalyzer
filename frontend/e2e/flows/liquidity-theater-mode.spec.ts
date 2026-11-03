import AxeBuilder from '@axe-core/playwright';

import { expect, test } from '../fixtures';
import { API_ORIGIN } from '../fixtures/env';

/**
 * The liquidity timeline in theater mode (tasks/todo/LiquidityTheaterMode.md): the chart over the whole viewport,
 * Esc and × to leave, `?view=theater` to come back; the legend with a deal's overdue rows and "Remove from
 * timeline"; the deals sheet with a one-tap milestone Done; the hover preview and the day modal. The browser clock
 * is frozen on 2026-09-04 (fixtures/clock.ts).
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

test('theater mode covers the viewport; Esc and × leave it, and ?view=theater brings it back', async ({ page, request, settle }) => {
  await seedSettings(request);
  await seedTransaction(request, '2026-09-10', -1200, 'Plumber');

  await page.goto('/liquidity');
  await page.getByTestId('liquidity.theater-open').click();
  const theater = page.getByTestId('theater.root');
  await expect(theater).toBeVisible();
  await expect(page).toHaveURL(/[?&]view=theater/);

  // The chart spans the viewport's width: no app sidebar, no Upcoming rail beside it.
  const viewportWidth = page.viewportSize()!.width;
  const chartBox = (await theater.getByTestId('chart.container').boundingBox())!;
  expect(chartBox.width).toBeGreaterThan(viewportWidth - 2);
  await expect(theater.locator('[data-part="today-pill"]')).toHaveCount(1);

  await page.keyboard.press('Escape');
  await settle(TRANSITION_MS);
  await expect(theater).toHaveCount(0);
  await expect(page).not.toHaveURL(/view=theater/);

  await page.goto('/liquidity?view=theater');
  await expect(theater).toBeVisible();
  await theater.getByTestId('theater.close').click();
  await settle(TRANSITION_MS);
  await expect(theater).toHaveCount(0);
  await expect(page).toHaveURL(/\/liquidity$/);
});

test('the legend lists a deal with its overdue rows; Done clears one, and the deal can leave the timeline', async ({ page, seed, request, dialogs, settle }) => {
  await seedSettings(request);
  const deal = await seed.seedActiveDeal('BRRRR', DEAL_WITH_OVERDUE_ROWS);
  await importDeal(request, deal.id);

  await page.goto('/liquidity?view=theater');
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

  await page.goto('/liquidity?view=theater');
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

test('hovering a day previews it; a click opens the day in full, with every action', async ({ page, request, settle }, testInfo) => {
  test.skip(testInfo.project.name.startsWith('Mobile'), 'hover is a desktop pointer gesture');
  await seedSettings(request);
  const plumberId = await seedTransaction(request, TODAY, -1200, 'Plumber');

  await page.goto('/liquidity?view=theater');
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

test('theater mode has no serious accessibility violations', async ({ page, seed, request, settle }, testInfo) => {
  test.skip(testInfo.project.name !== 'chromium', 'axe runs on chromium only');
  await seedSettings(request);
  const deal = await seed.seedActiveDeal('BRRRR', DEAL_WITH_OVERDUE_ROWS);
  await importDeal(request, deal.id);

  await page.goto('/liquidity?view=theater');
  await openLegend(page, settle);
  await page.getByTestId('theater.sheet.toggle').click();
  // axe schedules its work on timers: let the frozen clock run.
  await page.clock.resume();
  const results = await new AxeBuilder({ page }).include('[data-testid="theater.root"]').analyze();
  const seriousViolations = results.violations.filter((violation) => violation.impact === 'serious' || violation.impact === 'critical');
  expect(seriousViolations.map((violation) => `${violation.id}: ${violation.nodes.map((node) => node.target.join(' ')).join(', ')}`)).toEqual([]);
});
