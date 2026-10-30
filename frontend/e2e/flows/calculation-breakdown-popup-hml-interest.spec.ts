import { expect, test } from '../fixtures';

/**
 * The calculation breakdown popup on a Bought deal's Cash Out tile.
 *
 * "HML Interest paid monthly" used to be a raw operand of Total Cash Invested
 * with no step behind it, so the row could not be expanded. The backend now
 * files it as its own step (the per diem × the real days of each month, paid
 * on the 1st after it), and the popup opens it like any other computed operand.
 */

async function openBoughtDealModal(page: import('@playwright/test').Page, dealId: string, settle: (ms: number) => Promise<void>) {
  await page.goto('/bought-deals');
  await page.getByTestId(`boughtdeals.card.${dealId}`).click();
  await expect(page.getByTestId('boughtdeals.modal')).toBeVisible();
  await settle(400);
}

test('the Cash Out popup expands HML Interest paid monthly into the per diem × the days of each month', async ({
  page,
  seed,
  settle,
}) => {
  const deal = await seed.seedBoughtDeal('BRRRR');
  await openBoughtDealModal(page, deal.id, settle);
  await page.getByTestId('result-tile.cash_out.show-calculation').click();
  const popup = page.getByTestId('calculation-breakdown-popup');
  await expect(popup).toBeVisible();

  // The headline's operands open expanded; Total Cash Invested lists HML Interest paid monthly.
  await expect(popup.getByRole('button', { name: 'Hide how Total Cash Invested is calculated' })).toBeVisible();
  const showHmlInterestPaidMonthly = popup.getByRole('button', { name: 'Show how HML Interest paid monthly is calculated' });
  await expect(showHmlInterestPaidMonthly).toBeVisible();
  await showHmlInterestPaidMonthly.click();

  await expect(popup).toContainText('paid on the 1st after it');
  await expect(popup).toContainText('payments on the 1sts from');
});
