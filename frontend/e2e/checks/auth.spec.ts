import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { test, expect } from '../fixtures';
import { API_ORIGIN } from '../fixtures/env';

/**
 * Passkeys end to end, on chromium's virtual authenticator: an enrollment
 * link from `manage.py enroll` creates a passkey and a session; signing out
 * and back in works with the discoverable credential; a session survives a
 * reload. The backend runs with AUTH_MODE unset (off), so nothing else in the
 * suite sees a login screen -- exactly what an un-migrated deployment sees.
 */

const BACKEND = fileURLToPath(new URL('../../../BackEnd', import.meta.url));
const TEST_DB = process.env.TEST_DATABASE_URL || 'postgresql+psycopg2://brrrr_test:brrrr_test@127.0.0.1:55432/brrrr_test';

function enrollmentLink(username: string): string {
  const out = execFileSync('python3', ['-m', 'manage', 'enroll', username, '--reps-user', 'Aviv2026', '--display-name', 'E2E'], {
    cwd: BACKEND,
    env: { ...process.env, DATABASE_URL: TEST_DB, PYTHONDONTWRITEBYTECODE: '1', APP_ENV: 'development', AUTH_APP_ORIGIN: 'http://localhost:5173' },
    encoding: 'utf8',
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  const link = out.trim().split('\n').pop()!;
  expect(link).toContain('/enroll?token=');
  return link;
}

test.describe('passkeys', () => {
  test.skip(({ browserName }) => browserName !== 'chromium', 'virtual authenticator needs CDP');

  test('enroll with a link, sign out, sign back in, survive a reload', async ({ page, context }) => {
    const cdp = await context.newCDPSession(page);
    await cdp.send('WebAuthn.enable');
    await cdp.send('WebAuthn.addVirtualAuthenticator', {
      options: { protocol: 'ctap2', transport: 'internal', hasResidentKey: true, hasUserVerification: true, isUserVerified: true, automaticPresenceSimulation: true },
    });

    const link = enrollmentLink(`e2e-${Date.now()}`);
    await page.goto(link.replace('http://localhost:5173', ''));
    await expect(page.getByTestId('enroll.page')).toBeVisible();
    await page.getByTestId('enroll.label').fill('Playwright');
    await page.getByTestId('enroll.create').click();
    await expect(page).toHaveURL(/\/$/);

    // The session cookies are set and /auth/me knows us.
    const me = await page.request.get(`${API_ORIGIN}/auth/me`);
    expect(me.ok()).toBe(true);
    expect((await me.json()).user.display_name).toBe('E2E');

    // Sign in again with the discoverable credential after a logout.
    await page.request.delete(`${API_ORIGIN}/auth/session`, { headers: { 'X-Requested-With': 'XMLHttpRequest' } });
    expect((await page.request.get(`${API_ORIGIN}/auth/me`)).status()).toBe(401);
    await page.goto('/login');
    await expect(page.getByTestId('login.page')).toBeVisible();
    await page.getByTestId('login.passkey').click();
    await expect(page).toHaveURL(/\/$/);
    expect((await page.request.get(`${API_ORIGIN}/auth/me`)).ok()).toBe(true);

    await page.reload();
    expect((await page.request.get(`${API_ORIGIN}/auth/me`)).ok()).toBe(true);
  });

  test('a used enrollment link is refused', async ({ page, context }) => {
    const cdp = await context.newCDPSession(page);
    await cdp.send('WebAuthn.enable');
    await cdp.send('WebAuthn.addVirtualAuthenticator', {
      options: { protocol: 'ctap2', transport: 'internal', hasResidentKey: true, hasUserVerification: true, isUserVerified: true, automaticPresenceSimulation: true },
    });
    const link = enrollmentLink(`e2e-${Date.now()}`);
    await page.goto(link.replace('http://localhost:5173', ''));
    await page.getByTestId('enroll.create').click();
    await expect(page).toHaveURL(/\/$/);
    await page.goto(link.replace('http://localhost:5173', ''));
    await page.getByTestId('enroll.create').click();
    await expect(page.getByTestId('enroll.error')).toContainText('invalid or has expired');
  });
});
