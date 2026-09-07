import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { test, expect } from '../fixtures';
import { API_ORIGIN } from '../fixtures/env';

/**
 * The production Content-Security-Policy (frontend/public/_headers, applied by
 * Netlify) is replayed on every document the built app serves, and every
 * route is walked with a real backend: one violation fails the check. The
 * policy names the production API host and localhost:8000; the e2e backend
 * listens elsewhere, so only that origin is substituted.
 */

const HEADERS = fileURLToPath(new URL('../../public/_headers', import.meta.url));

function policy(): string {
  const line = readFileSync(HEADERS, 'utf8')
    .split('\n')
    .find((l) => l.trim().startsWith('Content-Security-Policy:'));
  expect(line, 'an enforcing Content-Security-Policy line in public/_headers').toBeTruthy();
  const value = line!.trim().slice('Content-Security-Policy:'.length).trim();
  expect(value).not.toContain("'unsafe-eval'");
  expect(value).toContain("frame-ancestors 'none'");
  return value.replace('http://localhost:8000', API_ORIGIN);
}

const ROUTES: [path: string, ready: string][] = [
  ['/', 'landing.offer'],
  ['/analyze', 'form.root'],
  ['/my-deals', 'mydeals.add-deal'],
  ['/bought-deals', 'boughtdeals.edit-pipeline'],
  ['/liquidity', 'liquidity.add-flow'],
  ['/reps', 'reps.manual-entry'],
];

test('every route renders under the production CSP without a violation', async ({ page }) => {
  const csp = policy();
  await page.route('**/*', async (route) => {
    if (route.request().resourceType() !== 'document') return route.continue();
    const response = await route.fetch();
    await route.fulfill({ response, headers: { ...response.headers(), 'content-security-policy': csp } });
  });
  await page.addInitScript(() => {
    (window as any).__csp = [];
    document.addEventListener('securitypolicyviolation', (e) => {
      (window as any).__csp.push(`${e.violatedDirective} blocked ${e.blockedURI || 'inline'} at ${e.sourceFile || e.documentURI}`);
    });
  });
  const consoleErrors: string[] = [];
  page.on('console', (m) => {
    if (m.type() === 'error' && /Content Security Policy/i.test(m.text())) consoleErrors.push(m.text());
  });

  for (const [path, ready] of ROUTES) {
    await page.goto(path);
    await expect(page.getByTestId(ready)).toBeVisible();
    const violations: string[] = await page.evaluate(() => (window as any).__csp);
    expect(violations, `${path} violated the CSP`).toEqual([]);
  }
  expect(consoleErrors).toEqual([]);
});
