import { expect, test } from '../fixtures';
import { API_ORIGIN } from '../fixtures/env';

/**
 * Opening the site after the 15-minute access cookie expired
 * (tasks/todo/DashboardDataMissingOnFirstOpen.md).
 *
 * The suite's backend runs with AUTH_MODE off, so the session side of
 * production is played by `page.route`: sessions are enforced, `/auth/me`
 * and every data route answer 401 until `/auth/refresh` renews the session,
 * exactly like a browser whose access cookie is gone but whose refresh cookie
 * is still valid. Once renewed, `/active-deals` reaches the real backend.
 *
 * Before the fix the dashboard fetched the deals before the session was
 * renewed, the 401 was never retried, and the tiles read 0 until a reload.
 */

const TRUSTED_SESSION = {
  status: 'ok',
  user: { id: 'e2e-user', username: 'e2e', display_name: 'E2E', reps_user: null, role: 'owner' },
  device_id: 'e2e-device',
  device_status: 'trusted',
  auth_mode: 'enforce',
  device_policy: 'off',
};

test('dashboard shows the deals on the first open after the access cookie expired, without a reload', async ({ page, seed }) => {
  await seed.seedActiveDeal('BRRRR', { section: 1 });
  await seed.seedActiveDeal('BRRRR', { section: 2 });

  let isSessionRenewed = false;
  let refreshCallCount = 0;
  const unauthenticated = { status: 401, contentType: 'application/json', body: JSON.stringify({ detail: 'unauthenticated' }) };

  await page.route(`${API_ORIGIN}/auth/config`, (route) =>
    route.fulfill({ contentType: 'application/json', body: JSON.stringify({ auth_mode: 'enforce', device_policy: 'off', rp_id: 'localhost' }) }),
  );
  await page.route(`${API_ORIGIN}/auth/me`, (route) =>
    isSessionRenewed ? route.fulfill({ contentType: 'application/json', body: JSON.stringify(TRUSTED_SESSION) }) : route.fulfill(unauthenticated),
  );
  await page.route(`${API_ORIGIN}/auth/refresh`, (route) => {
    refreshCallCount += 1;
    isSessionRenewed = true;
    return route.fulfill({ contentType: 'application/json', body: JSON.stringify(TRUSTED_SESSION) });
  });
  await page.route(`${API_ORIGIN}/active-deals`, (route) => (isSessionRenewed ? route.continue() : route.fulfill(unauthenticated)));
  // The real Member Loan route always wants a real passkey session, which this
  // fake one is not; answer it as production answers a signed-in non-member.
  await page.route(`${API_ORIGIN}/member-loan/access`, (route) =>
    isSessionRenewed ? route.fulfill({ status: 403, contentType: 'application/json', body: JSON.stringify({ detail: 'member_loan_access_denied' }) }) : route.fulfill(unauthenticated),
  );

  await page.goto('/');

  await expect(page.getByTestId('landing.card.My Deals')).toContainText('2');
  // One renewal only: a second refresh with the same token is a replay and the API would revoke the session.
  expect(refreshCallCount).toBe(1);
  await expect(page).toHaveURL(/\/$/);
});
