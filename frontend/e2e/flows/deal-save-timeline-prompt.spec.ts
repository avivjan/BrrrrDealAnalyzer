import { expect, test } from '../fixtures';
import { API_ORIGIN } from '../fixtures/env';
import { fieldInput, setField } from '../fixtures/form';

/**
 * A save that changes an imported deal's rows asks at once ("This changes the liquidity timeline"), and a Bought deal
 * form loaded before the deal changed elsewhere cannot overwrite it (tasks/todo/ConstructionAccountPerRehab.md,
 * Step D). The browser clock is frozen on 2026-09-04 (fixtures/clock.ts).
 */

const SEED_HEADERS = { 'x-e2e-seed': '1' };
const AUTOSAVE_MS = 2500;
const TRANSITION_MS = 400;
const DEAL_DATES_AFTER_TODAY = { contractDate: '2026-08-28', buyClosingDate: '2026-09-10', address: '9 Prompt Court' };

type Request = import('@playwright/test').APIRequestContext;
type Seed = { seedBoughtDeal: (type: 'BRRRR', overrides: Record<string, unknown>) => Promise<{ id: string }> };

async function seedImportedBoughtDeal(request: Request, seed: Seed) {
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

test('saving an imported deal asks at once; Cancel asks again when Liquidity opens; Confirm updates the timeline', async ({ page, seed, request, settle }) => {
  const deal = await seedImportedBoughtDeal(request, seed);

  await page.goto(`/bought-deals?openDeal=${deal.id}&dealType=BRRRR`);
  await expect(page.getByTestId('boughtdeals.modal')).toBeVisible();
  await settle(300);
  await setField(page, 'rehabCushion', 9000);
  await settle(AUTOSAVE_MS);

  const prompt = page.getByTestId('timeline-prompt.root');
  await expect(prompt).toBeVisible();
  await expect(prompt.getByTestId('timeline-prompt.confirm')).toBeEnabled();
  await prompt.getByTestId('timeline-prompt.cancel').click();
  await settle(TRANSITION_MS);
  await expect(prompt).toHaveCount(0);

  await page.goto('/liquidity');
  await expect(prompt).toBeVisible();
  await expect(prompt.getByTestId('timeline-prompt.confirm')).toBeEnabled();
  await prompt.getByTestId('timeline-prompt.confirm').click();
  await settle(TRANSITION_MS);
  await expect(prompt).toHaveCount(0);
  await expect(page.getByTestId('timeline-notice.message')).toContainText('Liquidity timeline updated');

  await page.goto('/liquidity');
  await settle(TRANSITION_MS);
  await expect(prompt).toHaveCount(0);   // nothing left out of date
});

test('a Bought deal form loaded before the deal changed elsewhere is refused and refreshed', async ({ page, seed, request, settle }) => {
  const deal = await seedImportedBoughtDeal(request, seed);

  await page.goto(`/bought-deals?openDeal=${deal.id}&dealType=BRRRR`);
  await expect(page.getByTestId('boughtdeals.modal')).toBeVisible();
  await settle(300);

  // Elsewhere (another tab, the Construction Accounts card): the cushion becomes $7,000.
  const deals = await (await request.get(`${API_ORIGIN}/bought-deals`, { headers: SEED_HEADERS })).json() as { id: string }[];
  const changedElsewhere = await request.put(`${API_ORIGIN}/bought-deals/${deal.id}`, {
    headers: SEED_HEADERS, data: { ...deals.find(d => d.id === deal.id), rehabCushion: 7000 },
  });
  expect(changedElsewhere.ok()).toBe(true);

  await setField(page, 'rehabCushion', 9000);
  await settle(AUTOSAVE_MS);
  await expect(page.getByTestId('boughtdeals.modal.stale-form')).toHaveText('This deal was changed elsewhere; your form was refreshed.');
  await expect(fieldInput(page, 'rehabCushion')).toHaveValue(/7,?000/);
  const stored = await (await request.get(`${API_ORIGIN}/bought-deals`, { headers: SEED_HEADERS })).json() as { id: string; rehabCushion: number }[];
  expect(Number(stored.find(d => d.id === deal.id)!.rehabCushion)).toBe(7000);
});
