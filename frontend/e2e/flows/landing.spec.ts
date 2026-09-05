import { checkA11y, expect, test } from '../fixtures';

/**
 * The landing page: what loads, what it asks the server for, and that every
 * feature card is on screen. `App.vue` pings `/helloworld` and pre-fetches
 * `/active-deals` for the portfolio bar on *every* route, so those two are the
 * baseline of every contract in this suite.
 */

const FEATURE_CARDS = [
  'REPS Tracker',
  'Daily Tasks',
  'Stessa',
  'Analyze Deal',
  'My Deals',
  'Bought Deals',
  'Liquidity',
];

test('landing page loads, calls helloworld + active-deals, shows every card', async ({
  page,
  api,
}) => {
  await page.goto('/');

  await expect(page.getByTestId('app.status')).toBeVisible();
  await expect(page.getByTestId('landing.offer')).toBeVisible();

  for (const title of FEATURE_CARDS) {
    await expect(page.getByTestId(`landing.card.${title}`)).toBeVisible();
  }

  await api.expectContract('landing-load');

  // Always last: the scan resumes the frozen clock.
  await checkA11y(page, 'landing');
});
