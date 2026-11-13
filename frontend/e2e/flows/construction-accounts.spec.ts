import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import type { APIRequestContext, BrowserContext, Page } from '@playwright/test';

import { expect, test } from '../fixtures';
import { API_ORIGIN } from '../fixtures/env';

/**
 * The Construction Accounts page against the fake Mercury of e2e/backend/fake_mercury.py
 * (tasks/todo/ConstructionAccountPerRehab.md, Step H): linking mid-rehab, every edit asking first, one notice that
 * updates in place, a Deposit with the passkey step-up, the bank's own changes, and instant updates.
 *
 * The fake is one LLC, E2E: a checking (E2E Checking, $80,000), a construction account (Oak Rehab Construction, $0)
 * and a tax bucket ($4,000). The browser clock is frozen on 2026-09-04 (fixtures/clock.ts); specs advance it with
 * `settle(ms)` to run the page's own timers (the poll, the 5-second instant-update check).
 */

const SEED_HEADERS = { 'x-e2e-seed': '1' };
const TRANSITION_MS = 400;
/** Budget $70,000, rehab $50,000 (no contingency), cushion $5,000: $5,000 to deposit, $25,000 back at rehab end. */
const DEAL = { contractDate: '2026-08-28', buyClosingDate: '2026-09-10', address: '18 Oak Rehab Rd', rehabCost: 50, rehabContingency: 0, constructionLoanBudget: 70 };
const BACKEND = fileURLToPath(new URL('../../../BackEnd', import.meta.url));
const TEST_DB = process.env.TEST_DATABASE_URL || 'postgresql+psycopg2://brrrr_test:brrrr_test@127.0.0.1:55432/brrrr_test';

type Seed = { seedBoughtDeal: (type: 'BRRRR', overrides: Record<string, unknown>) => Promise<{ id: string }> };

async function fakeMercury(request: APIRequestContext, path: string, data?: unknown) {
  const response = data === undefined
    ? await request.get(`${API_ORIGIN}/e2e/fake-mercury/${path}`, { headers: SEED_HEADERS })
    : await request.post(`${API_ORIGIN}/e2e/fake-mercury/${path}`, { headers: SEED_HEADERS, data });
  expect(response.ok(), await response.text()).toBe(true);
  return response.json();
}

/** A Bought BRRRR deal in the timeline, its construction account linked through the API. */
async function seedLinkedDeal(request: APIRequestContext, seed: Seed, link = true): Promise<string> {
  const settings = await request.put(`${API_ORIGIN}/liquidity/settings`, {
    headers: SEED_HEADERS,
    data: { opening_balance_dollars: 150000, opening_balance_date: '2026-09-04', reserve_dollars: 5000, construction_account_refresh_interval_seconds: 30 },
  });
  expect(settings.ok()).toBe(true);
  const deal = await seed.seedBoughtDeal('BRRRR', DEAL);
  expect((await request.post(`${API_ORIGIN}/liquidity/deals/bought/${deal.id}/import`, { headers: SEED_HEADERS, data: { today: '2026-09-04' } })).ok()).toBe(true);
  if (link) {
    const linked = await request.put(`${API_ORIGIN}/liquidity/construction-accounts/${deal.id}`, {
      headers: SEED_HEADERS, params: { today: '2026-09-04' },
      data: { construction_mercury_account_id: 'e2e-construction', primary_checking_mercury_account_id: 'e2e-checking' },
    });
    expect(linked.ok(), await linked.text()).toBe(true);
  }
  return deal.id;
}

/** The owner on chromium's virtual authenticator: Deposit and instant updates ask for the passkey. */
async function signInTheOwner(context: BrowserContext, page: Page): Promise<void> {
  const out = execFileSync('python3', ['-m', 'manage', 'enroll', 'e2e-owner', '--display-name', 'E2E Owner'], {
    cwd: BACKEND,
    env: { ...process.env, DATABASE_URL: TEST_DB, PYTHONDONTWRITEBYTECODE: '1', APP_ENV: 'development', AUTH_APP_ORIGIN: 'http://localhost:5173' },
    encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'],
  });
  const cdp = await context.newCDPSession(page);
  await cdp.send('WebAuthn.enable');
  await cdp.send('WebAuthn.addVirtualAuthenticator', {
    options: { protocol: 'ctap2', transport: 'internal', hasResidentKey: true, hasUserVerification: true, isUserVerified: true, automaticPresenceSimulation: true },
  });
  await page.goto(out.trim().split('\n').pop()!.replace('http://localhost:5173', ''));
  await page.getByTestId('enroll.label').fill('Playwright');
  await page.getByTestId('enroll.create').click();
  await expect(page).toHaveURL(/\/$/);
}

async function openTheCard(page: Page, dealId: string) {
  await page.goto(`/liquidity/construction-accounts?deal=${dealId}`);
  const card = page.getByTestId(`ca.${dealId}`);
  await expect(card).toBeVisible();
  // The page's first Mercury read must land before a spec changes the fake bank: a read that saw the balance before
  // a change and the transactions after it would report a change that never happened.
  await page.waitForLoadState('networkidle');
  return card;
}

/** Confirm the open prompt and wait until it is gone (the save lands, then its window leaves on the paused clock). */
async function confirmThePrompt(page: Page, settle: (ms: number) => Promise<void>) {
  const prompt = page.getByTestId('timeline-prompt.root');
  await expect(prompt.getByTestId('timeline-prompt.confirm')).toBeEnabled();
  await prompt.getByTestId('timeline-prompt.confirm').click();
  await expect.poll(async () => { await settle(TRANSITION_MS); return prompt.count(); }).toBe(0);
}

/** Tap a figure, type, Enter. */
async function editFigure(page: Page, hook: string, value: string) {
  await page.getByTestId(hook).click();
  const input = page.getByTestId(`${hook}.input`);
  await input.fill(value);
  await input.press('Enter');
}

test.beforeEach(async ({ request }) => {
  await fakeMercury(request, 'reset', { on: true });
});

test.afterEach(async ({ request }) => {
  await fakeMercury(request, 'reset', { on: false });
});

test('link a construction account mid-rehab: the page is in the sidebar and on the Liquidity bar, and linking asks first', async ({ page, seed, request, settle, isMobile }) => {
  const dealId = await seedLinkedDeal(request, seed, false);

  await page.goto('/liquidity');
  if (isMobile) {   // on a phone the link is in the ⋯ menu
    await page.getByTestId('theater.more').click();
    await page.getByTestId('theater.more.construction-accounts').click();
  } else {
    await page.getByTestId('theater.construction-accounts').click();
  }
  await expect.poll(() => new URL(page.url()).pathname).toBe('/liquidity/construction-accounts');
  if (!isMobile) {
    await page.goto('/');
    await page.getByTestId('shell.nav.construction-accounts').click();
    await expect.poll(() => new URL(page.url()).pathname).toBe('/liquidity/construction-accounts');
  }

  await page.getByTestId(`ca.${dealId}.link`).click();
  await page.getByTestId('ca-link.construction-account').selectOption('e2e-construction');
  await page.getByTestId('ca-link.checking-account').selectOption('e2e-checking');
  await page.getByTestId('ca-link.draws-before').fill('10000');
  await page.getByTestId('ca-link.save').click();

  await expect(page.getByTestId('timeline-prompt.root')).toBeVisible();
  await confirmThePrompt(page, settle);
  await expect(page.getByTestId(`ca.${dealId}.state`)).not.toHaveText('Not linked');
  await expect(page.getByTestId(`ca.${dealId}.balance`)).toBeVisible();
  // No sideways scroll on a phone: the longest page title must not widen the shell (it truncates in the top bar).
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(page.viewportSize()!.width);
});

test('an edit that moves the timeline asks first: Cancel keeps it, Confirm saves it; one notice for several edits', async ({ page, seed, request, settle }) => {
  const dealId = await seedLinkedDeal(request, seed);
  await openTheCard(page, dealId);
  await page.getByTestId(`ca.${dealId}.rehab`).locator('summary').click();

  const hook = `ca.${dealId}.actual-rehab-cost`;
  const before = await page.getByTestId(hook).innerText();
  await editFigure(page, hook, '58000');
  const prompt = page.getByTestId('timeline-prompt.root');
  await expect(prompt).toBeVisible();
  await expect(prompt.getByTestId('timeline-prompt.figure.Rehab cost')).toContainText('$58,000');
  await prompt.getByTestId('timeline-prompt.cancel').click();
  await settle(TRANSITION_MS);
  await expect(page.getByTestId(hook)).toHaveText(before);

  await editFigure(page, hook, '58000');
  await confirmThePrompt(page, settle);
  await expect(page.getByTestId(hook)).toContainText('58,000');
  await expect(page.getByTestId('timeline-notice.message')).toHaveText(/Liquidity timeline updated: \d+ rows?/);

  // The cushion is the Bought deal's own figure: edited here, it is the deal's; a second edit updates the same notice.
  await editFigure(page, `ca.${dealId}.cushion`, '7000');
  await confirmThePrompt(page, settle);
  await expect(page.getByTestId('timeline-notice')).toHaveCount(1);
  await expect(page.getByTestId('timeline-notice.message')).toContainText('2 edits');
  const deals = await (await request.get(`${API_ORIGIN}/bought-deals`, { headers: SEED_HEADERS })).json() as { id: string; rehabCushion: number }[];
  expect(Number(deals.find(deal => deal.id === dealId)!.rehabCushion)).toBe(7000);

  // The buffer to keep moves no timeline row: saved at once, no prompt.
  await editFigure(page, `ca.${dealId}.buffer`, '1000');
  await expect(page.getByTestId('timeline-notice.message')).toHaveText('Saved');
  await expect(prompt).toHaveCount(0);
});

test('Deposit asks for the passkey, sends once, and marks the deposit row done', async ({ page, context, seed, request, settle }) => {
  const dealId = await seedLinkedDeal(request, seed);
  await signInTheOwner(context, page);
  await openTheCard(page, dealId);

  await page.getByTestId(`ca.${dealId}.deposit`).click();
  const transfer = page.getByTestId('ca-transfer.root');
  await expect(transfer).toBeVisible();
  await expect(page.getByTestId('ca-transfer.amount')).toHaveValue('5000');
  await expect(page.getByTestId('ca-transfer.marked-done')).toBeVisible();
  await page.getByTestId('ca-transfer.send').click();
  await expect(page.getByTestId('ca-transfer.outcome')).toHaveAttribute('data-outcome', 'accepted_by_mercury');
  expect((await fakeMercury(request, 'calls')).transfers).toBe(1);
  await page.getByTestId('ca-transfer.close').click();
  await settle(TRANSITION_MS);
  await expect(transfer).toHaveCount(0);

  await page.getByTestId(`ca.${dealId}.timeline-rows`).locator('summary').click();
  await expect(page.getByTestId(`ca.${dealId}.timeline-row.construction_account_deposit`)).toContainText('Done');
});

test('the bank: a draw shows within one poll with no window; a steal made in Mercury opens "updated from the bank"', async ({ page, seed, request, settle }) => {
  const dealId = await seedLinkedDeal(request, seed);
  await openTheCard(page, dealId);

  await fakeMercury(request, 'transaction', { account_id: 'e2e-construction', transaction_id: 'draw-1', signed_amount_dollars: 30000, counterparty_name: 'Lender' });
  await settle(31_000);
  await expect(page.getByTestId(`ca.${dealId}.balance`)).toContainText('30,000');
  await expect(page.getByTestId('timeline-prompt.root')).toHaveCount(0);

  await fakeMercury(request, 'transaction', { account_id: 'e2e-construction', transaction_id: 'steal-in-mercury', signed_amount_dollars: -10000, internal: true });
  await settle(31_000);
  const bankReport = page.getByTestId('timeline-prompt.root');
  await expect(bankReport).toBeVisible();
  await expect(bankReport.getByTestId('timeline-prompt.ok')).toBeVisible();
  await bankReport.getByTestId('timeline-prompt.ok').click();
});

test('instant updates: the drawer turns them on, a signed event shows at once, a wrongly signed one is recorded', async ({ page, context, seed, request, settle }) => {
  await seedLinkedDeal(request, seed);
  await signInTheOwner(context, page);
  await page.goto('/liquidity/construction-accounts?open=settings');
  const workspace = page.getByTestId('ca-settings.workspace.E2E');
  await expect(workspace).toBeVisible();
  await workspace.getByTestId('ca-settings.workspace.E2E.turn-on').click();
  await expect(page.getByTestId('ca-settings.workspace.E2E.instant')).toContainText('waiting for the first event');

  const event = await fakeMercury(request, 'signed-event', { wrong_signature: false });
  const accepted = await request.post(`${API_ORIGIN}${event.path}`, { data: event.body, headers: { 'Content-Type': 'application/json', 'Mercury-Signature': event.signature } });
  expect(accepted.status()).toBe(200);
  const forged = await fakeMercury(request, 'signed-event', { wrong_signature: true });
  const refused = await request.post(`${API_ORIGIN}${forged.path}`, { data: forged.body, headers: { 'Content-Type': 'application/json', 'Mercury-Signature': forged.signature } });
  expect(refused.status()).toBe(401);

  await page.goto('/liquidity/construction-accounts?open=settings');   // the page clears ?open= once it opened the drawer
  await settle(TRANSITION_MS);
  await expect(page.getByTestId('ca-settings.workspace.E2E.instant')).toContainText('last instant event');
  await expect(page.getByTestId('ca-settings.workspace.E2E.error')).toContainText('wrong signature');
});

test('a signed event after money lands in checking moves the Liquidity cash balance with no reload and no prompt', async ({ page, context, seed, request, settle }) => {
  await seedLinkedDeal(request, seed);
  await signInTheOwner(context, page);
  await page.goto('/liquidity/construction-accounts?open=settings');
  await page.getByTestId('ca-settings.workspace.E2E.turn-on').click();
  await expect(page.getByTestId('ca-settings.workspace.E2E.instant')).toContainText('waiting for the first event');

  await page.goto('/liquidity');
  const balance = page.getByTestId('theater.figure.balance');
  await expect(balance).toContainText('$');
  await settle(TRANSITION_MS);
  const dollarsOf = async () => Number((await balance.innerText()).replace(/[^0-9.-]/g, ''));
  const balanceBefore = await dollarsOf();

  await fakeMercury(request, 'balance', { account_id: 'e2e-checking', balance_dollars: 92000 });
  const event = await fakeMercury(request, 'signed-event', { wrong_signature: false });
  expect((await request.post(`${API_ORIGIN}${event.path}`, { data: event.body, headers: { 'Content-Type': 'application/json', 'Mercury-Signature': event.signature } })).status()).toBe(200);
  await settle(6_000);   // the 5-second instant-update check, well before the 30-second poll
  await expect.poll(dollarsOf).toBe(balanceBefore + 12000);   // checking 80,000 -> 92,000; the construction account is never cash
  await expect(page.getByTestId('timeline-prompt.root')).toHaveCount(0);
});

test('the refresh interval set in the drawer is kept after a reload', async ({ page, seed, request, settle }) => {
  await seedLinkedDeal(request, seed);
  await page.goto('/liquidity/construction-accounts?open=settings');
  await settle(TRANSITION_MS);   // the drawer slides in on the paused clock
  // Nothing wider than the screen: on a phone a wider drawer pushed its own Save button out of view.
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(page.viewportSize()!.width);
  await page.getByTestId('ca-settings.refresh-interval').fill('45');
  await page.getByTestId('ca-settings.save').click();
  await settle(TRANSITION_MS);
  await page.goto('/liquidity/construction-accounts?open=settings');
  await expect(page.getByTestId('ca-settings.refresh-interval')).toHaveValue('45');
});
