import { expect, test } from '../fixtures';
import { API_ORIGIN } from '../fixtures/env';

/**
 * Wherever a deal, a row or an account is shown, one click reaches the same thing everywhere else
 * (tasks/todo/ConstructionAccountPerRehab.md, Step C0). The browser clock is frozen on 2026-09-04 (fixtures/clock.ts).
 */

const SEED_HEADERS = { 'x-e2e-seed': '1' };
const ADDRESS = '31 Shortcut Way';
const TRANSITION_MS = 400;
const DEAL_DATES_AFTER_TODAY = { contractDate: '2026-08-28', buyClosingDate: '2026-09-10', address: ADDRESS };

type Request = import('@playwright/test').APIRequestContext;

async function seedImportedBoughtDeal(request: Request, seed: { seedBoughtDeal: (type: 'BRRRR', overrides: Record<string, unknown>) => Promise<{ id: string }> }) {
  const settings = await request.put(`${API_ORIGIN}/liquidity/settings`, {
    headers: SEED_HEADERS,
    data: { opening_balance_dollars: 150000, opening_balance_date: '2026-09-04', reserve_dollars: 5000 },
  });
  expect(settings.ok()).toBe(true);
  const deal = await seed.seedBoughtDeal('BRRRR', DEAL_DATES_AFTER_TODAY);
  const imported = await request.post(`${API_ORIGIN}/liquidity/deals/bought/${deal.id}/import`, {
    headers: SEED_HEADERS,
    data: { today: '2026-09-04' },
  });
  expect(imported.ok()).toBe(true);
  return deal;
}

test('Bought deal → its timeline rows → its construction account → the deal again, and Back retraces each step', async ({ page, seed, request }) => {
  const deal = await seedImportedBoughtDeal(request, seed);

  await page.goto(`/bought-deals?openDeal=${deal.id}&dealType=BRRRR`);
  await expect(page.getByTestId('boughtdeals.modal')).toBeVisible();
  await expect.poll(() => new URL(page.url()).search).toBe('');

  await page.getByTestId('boughtdeals.modal').getByTestId('import-to-liquidity.on-the-timeline').click();
  await expect.poll(() => new URL(page.url()).pathname).toBe('/liquidity');
  const legendEntry = page.locator(`[data-testid="theater.legend.deal"][data-deal-key="bought:${deal.id}"]`);
  await expect(legendEntry.getByTestId('theater.legend.deal.toggle')).toHaveAttribute('aria-expanded', 'true');

  await legendEntry.getByTestId('theater.legend.deal.construction-account').click();
  await expect.poll(() => new URL(page.url()).pathname).toBe('/liquidity/construction-accounts');
  const card = page.getByTestId(`ca.${deal.id}`);
  await expect(card).toHaveAttribute('data-highlighted', 'true');

  await page.getByTestId(`ca.${deal.id}.open-deal`).click();
  await expect(page.getByTestId('boughtdeals.modal')).toBeVisible();

  await page.goBack();
  await expect.poll(() => new URL(page.url()).pathname).toBe('/liquidity/construction-accounts');
  await page.goBack();
  await expect.poll(() => new URL(page.url()).pathname).toBe('/liquidity');
  await page.goBack();
  await expect.poll(() => new URL(page.url()).pathname).toBe('/bought-deals');
});

test('a row of the day view opens its deal', async ({ page, seed, request }) => {
  const deal = await seedImportedBoughtDeal(request, seed);
  const transactions = await request.get(`${API_ORIGIN}/liquidity/transactions`, { headers: SEED_HEADERS });
  const dealRows = ((await transactions.json()) as { id: string; effective_date: string; source_deal_id?: string | null }[])
    // From today on: a row of a past milestone waits for its approval and is not on its day yet.
    .filter(row => row.source_deal_id === deal.id && row.effective_date >= '2026-09-04')
    .sort((a, b) => a.effective_date.localeCompare(b.effective_date));
  const row = dealRows[0]!;

  await page.goto(`/liquidity?transaction=${row.id}&day=${row.effective_date}`);
  await expect(page.getByTestId('theater.day-modal')).toBeVisible();
  await expect(page.getByTestId(`daydetail.txn.${row.id}`)).toHaveAttribute('data-highlighted', 'true');
  await page.getByTestId('theater.day-modal').getByTestId(`deal-tag.${row.id}`).click();
  await expect(page.getByTestId('boughtdeals.modal')).toBeVisible();
});

test('g then c opens Construction Accounts, and ⌘K finds a deal\'s construction account by its address', async ({ page, seed, request }) => {
  const deal = await seedImportedBoughtDeal(request, seed);

  await page.goto('/');
  await page.locator('body').press('g');
  await page.locator('body').press('c');
  await expect.poll(() => new URL(page.url()).pathname).toBe('/liquidity/construction-accounts');

  await page.goto('/');
  await page.keyboard.press('Control+k');
  await page.getByTestId('shell.command.input').fill(`${ADDRESS} construction`);
  await expect(page.getByTestId(`shell.command.item.deal-${deal.id}-construction-account`)).toBeVisible();
  await page.getByTestId('shell.command.input').press('Enter');
  await expect(page.getByTestId(`ca.${deal.id}`)).toHaveAttribute('data-highlighted', 'true');
});

test('a link to a deal that is no longer there says so', async ({ page }) => {
  await page.goto('/liquidity/construction-accounts?deal=00000000-0000-0000-0000-000000000000');
  await expect(page.getByTestId('ca.page.not-found')).toHaveText('That deal is no longer here.');
  await page.goto('/bought-deals?openDeal=00000000-0000-0000-0000-000000000000&dealType=BRRRR');
  await expect(page.getByTestId('boughtdeals.deep-link-not-found')).toHaveText('That deal is no longer here.');
});

test('the Bought card opens its construction account, and ? lists every shortcut', async ({ page, seed, request, settle }) => {
  const deal = await seedImportedBoughtDeal(request, seed);

  await page.goto('/bought-deals');
  await page.getByTestId(`boughtdeals.card.${deal.id}`).getByTestId('boughtcard.construction-account-link').click();
  await expect(page.getByTestId(`ca.${deal.id}`)).toHaveAttribute('data-highlighted', 'true');
  await expect(page.getByTestId('boughtdeals.modal')).toHaveCount(0);

  await page.locator('body').press('?');
  await expect(page.getByTestId('shell.shortcuts')).toBeVisible();
  await expect(page.getByTestId('shell.shortcuts.go-to.c')).toContainText('Construction accounts');
  await page.getByTestId('shell.shortcuts.close').click();
  await settle(TRANSITION_MS);
  await expect(page.getByTestId('shell.shortcuts')).toHaveCount(0);
});
