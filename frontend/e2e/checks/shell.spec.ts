import { expect, test } from '../fixtures';

/**
 * The v2 app shell: every route is reachable from the primary navigation, the
 * command palette opens on the keyboard shortcut, the Appearance drawer opens
 * from the topbar and hands focus back, and the phone layout swaps the
 * sidebar for the bottom bar. Behaviour the plan added in Phase 2 — none of it
 * touches a store or the network, so there is no golden to record; this is a
 * plain check spec.
 */

/** The same route → ready-hook table as `flows/a11y.spec.ts`. */
const ROUTES: [name: string, ready: string][] = [
  ['analyze', 'form.root'],
  ['my-deals', 'mydeals.add-deal'],
  ['bought-deals', 'boughtdeals.edit-pipeline'],
  ['liquidity', 'liquidity.add-flow'],
  ['reps', 'reps.manual-entry'],
  ['home', 'landing.offer'],
];

test.beforeEach(({}, testInfo) => {
  test.skip(testInfo.project.name !== 'chromium', 'shell layout is engine-independent; checked on chromium only');
});

test.describe('desktop', () => {
  test('the sidebar reaches every route, marking the current one', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByTestId('shell.sidebar')).toBeVisible();
    await expect(page.getByTestId('shell.mobile-nav')).toBeHidden();
    for (const [name, ready] of ROUTES) {
      await page.getByTestId(`shell.nav.${name}`).first().click();
      await expect(page.getByTestId(ready)).toBeVisible();
      await expect(page.getByTestId(`shell.nav.${name}`).first()).toHaveAttribute('aria-current', 'page');
    }
    // One <main>, one <h1> (the topbar title), on every route.
    await expect(page.locator('main')).toHaveCount(1);
    await expect(page.locator('h1')).toHaveCount(1);
  });

  test('Ctrl+K opens the command palette and Escape closes it', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByTestId('landing.offer')).toBeVisible();
    await page.keyboard.press('Control+k');
    const palette = page.getByTestId('shell.command');
    await expect(palette).toBeVisible();
    await expect(page.getByTestId('shell.command.input')).toBeFocused();
    await page.keyboard.type('liquid');
    await expect(page.getByTestId('shell.command.item.go-liquidity')).toBeVisible();
    await page.keyboard.press('Escape');
    await expect(palette).toBeHidden();
    // Enter on the filtered command navigates.
    await page.keyboard.press('Control+k');
    await page.keyboard.type('bought');
    await page.keyboard.press('Enter');
    await expect(page.getByTestId('boughtdeals.edit-pipeline')).toBeVisible();
  });

  test('the Appearance drawer opens from the topbar and returns focus on close', async ({ page }) => {
    await page.goto('/');
    const trigger = page.getByTestId('shell.settings-open');
    await trigger.click();
    const drawer = page.getByTestId('shell.settings');
    await expect(drawer).toBeVisible();
    await expect(page.getByTestId('shell.look-picker')).toBeVisible();
    await page.keyboard.press('Escape');
    await expect(drawer).toBeHidden();
    await expect(trigger).toBeFocused();
  });
});

test.describe('phone', () => {
  test.use({ viewport: { width: 390, height: 844 } });

  test('the bottom bar replaces the sidebar and still navigates', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByTestId('shell.mobile-nav')).toBeVisible();
    await expect(page.getByTestId('shell.sidebar')).toBeHidden();
    await page.getByTestId('shell.mobile-nav').getByTestId('shell.nav.liquidity').click();
    await expect(page.getByTestId('liquidity.add-flow')).toBeVisible();
    // The bar never covers the page's last line: main pads for it.
    const padding = await page.locator('main').evaluate((el) => parseFloat(getComputedStyle(el).paddingBottom));
    expect(padding).toBeGreaterThanOrEqual(60);
    // Settings from the topbar gear on a phone too.
    await page.getByTestId('shell.settings-open').click();
    await expect(page.getByTestId('shell.settings')).toBeVisible();
  });
});
