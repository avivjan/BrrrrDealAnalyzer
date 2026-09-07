import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { test, expect } from '../fixtures';
import { API_ORIGIN } from '../fixtures/env';

/**
 * The production Content-Security-Policy (frontend/public/_headers, applied by
 * Netlify) is what `vite preview` serves too (vite.config.ts), so the whole
 * browser suite already runs under it. This check pins that: the header the
 * preview sends is the file's policy (with the e2e API origin in the place of
 * localhost:8000), and every route plus the one blob: frame (the PDF preview)
 * renders without a single violation.
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

async function watchViolations(page: import('@playwright/test').Page) {
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
  const violations = async () => (await page.evaluate(() => (window as any).__csp)) as string[];
  return { violations, consoleErrors };
}

test('the app is served under the production CSP', async ({ page }) => {
  const response = await page.goto('/');
  expect(response?.headers()['content-security-policy']).toBe(policy());
});

test('every route renders under the production CSP without a violation', async ({ page }) => {
  const { violations, consoleErrors } = await watchViolations(page);
  for (const [path, ready] of ROUTES) {
    await page.goto(path);
    await expect(page.getByTestId(ready)).toBeVisible();
    expect(await violations(), `${path} violated the CSP`).toEqual([]);
  }
  expect(consoleErrors).toEqual([]);
});

test('the PDF preview (the one blob: frame) renders under the production CSP', async ({ page, seed }) => {
  const { violations, consoleErrors } = await watchViolations(page);
  const deal = await seed.seedActiveDeal('BRRRR', { section: 1 });
  await page.goto('/my-deals');
  await page.getByTestId(`mydeals.card.${deal.id}`).click();
  await expect(page.getByTestId('mydeals.modal')).toBeVisible();
  await page.getByTestId('mydeals.modal.view-report').click();
  await expect(page.getByTestId('mydeals.pdf-modal.iframe')).toHaveAttribute('src', /^blob:/);
  await page.waitForTimeout(500);
  expect(await violations(), 'the PDF preview violated the CSP').toEqual([]);
  expect(consoleErrors).toEqual([]);
});
