import { expect, test } from '../fixtures';

/**
 * The Cash Needed popup's "Cash schedule (Lowest ARV)" lists the deal's key dates among its cash
 * rows, so the schedule reads as a timeline. Each key date is a tinted uppercase marker with a flag
 * and no amount, listed first on its day.
 *
 * A deal under contract on 2026-08-25 that closes on 2026-09-04 completes its rehab 45 days later
 * (2026-10-19), has a tenant from 2026-12-03 (+90), pays the Nov 30 tax bill from its bucket inside
 * the hold, and refis on 2027-03-03 (+180).
 */
test('the Cash Needed schedule shows the deal’s key dates as markers among the transactions', async ({ page, seed, settle }) => {
  const deal = await seed.seedBoughtDeal('BRRRR', { contractDate: '2026-08-25', buyClosingDate: '2026-09-04', daysUntilRehabCompleted: 45 });
  await page.goto('/bought-deals');
  await page.getByTestId(`boughtdeals.card.${deal.id}`).click();
  await expect(page.getByTestId('boughtdeals.modal')).toBeVisible();
  await settle(400);
  await page.getByTestId('result-tile.total_cash_needed_for_deal.show-calculation').click();
  const schedule = page.getByTestId('calculation-breakdown-popup').getByTestId('cash-needed-schedule');
  await expect(schedule).toBeVisible();

  const milestones = schedule.locator('[data-part="schedule-milestone"]');
  await expect(milestones).toHaveText([
    /Aug 25, 2026\s*Contract signed/,
    /Sep 4, 2026\s*Purchase closing/,
    /Oct 19, 2026\s*Rehab completed/,
    /Nov 30, 2026\s*Property tax bill paid from the tax bucket \(Nov 30\)/,
    /Dec 3, 2026\s*Tenant moves in/,
    /Mar 3, 2027\s*Refi closing/,
  ]);

  // First on its day: the purchase closing sits right above the purchase wire.
  const purchaseClosing = schedule.locator('[data-milestone-key="purchase_closed"]');
  const lineKinds = await schedule.locator('tbody tr').evaluateAll((rows) =>
    rows.map((row) => row.getAttribute('data-milestone-key') ?? row.getAttribute('data-item-key')));
  expect(lineKinds[lineKinds.indexOf('purchase_closed') + 1]).toBe('cash_to_close_buy');
  expect(lineKinds.indexOf('contract_signed')).toBe(0);

  // A marker reads differently from a transaction: smaller, uppercase, no amount.
  const markerStyle = await purchaseClosing.locator('td').nth(1).evaluate((cell) => {
    const style = getComputedStyle(cell);
    return { textTransform: style.textTransform, fontSize: parseFloat(style.fontSize), colspan: cell.getAttribute('colspan') };
  });
  const transactionStyle = await schedule.locator('[data-item-key="cash_to_close_buy"] td').nth(1).evaluate((cell) => {
    const style = getComputedStyle(cell);
    return { textTransform: style.textTransform, fontSize: parseFloat(style.fontSize) };
  });
  expect(markerStyle).toMatchObject({ textTransform: 'uppercase', colspan: '2' });
  expect(transactionStyle.textTransform).toBe('none');
  expect(markerStyle.fontSize).toBeLessThan(transactionStyle.fontSize);
});
