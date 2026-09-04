import { expect, test } from '../fixtures';

/**
 * The liquidity timeline.
 *
 * Four requests on load, a Mercury sync that this environment always refuses,
 * an empty state that leads into settings, and then the two ways money enters
 * the timeline (a one-off and a recurring series). The chart is a `<canvas>`,
 * so its keyboard contract — arrow keys walk days and open the day panel — is
 * the only way a keyboard user reaches the data at all, and it is asserted
 * here rather than assumed.
 */

const MERCURY_OFFLINE_DETAIL =
  'No Mercury tokens found. Add MERCURY_API_TOKEN_<LABEL> entries ' +
  '(e.g. MERCURY_API_TOKEN_AJYK, MERCURY_API_TOKEN_AY) to BackEnd/.env.';

const MERCURY_SUCCESS = {
  total_balance_k: 61.5,
  total_available_k: 61.5,
  account_count: 2,
  workspace_count: 1,
  workspaces: [
    {
      workspace: 'BigWhales',
      total_balance_k: 61.5,
      total_available_k: 61.5,
      account_count: 2,
      accounts: [
        {
          id: 'acct-checking',
          name: 'Operating',
          type: 'checking',
          status: 'active',
          current_balance_k: 49.2,
          available_balance_k: 49.2,
          workspace: 'BigWhales',
        },
        {
          id: 'acct-reserve',
          name: 'Reserve',
          type: 'savings',
          status: 'active',
          current_balance_k: 12.3,
          available_balance_k: 12.3,
          workspace: 'BigWhales',
        },
      ],
    },
  ],
  workspace_errors: [],
  accounts: [],
};

type Page = import('@playwright/test').Page;
type Settle = (ms: number) => Promise<void>;

/**
 * These modals leave through a Vue `<Transition>`, and Vue drives one with
 * `requestAnimationFrame` — which the frozen clock also freezes. Without a
 * `settle` the backdrop never unmounts and swallows the next click, so every
 * modal dismissal here is followed by enough fake time for the 200 ms
 * transition to finish.
 */
const TRANSITION_MS = 400;

/** Below this the right-hand sidebar is `hidden` (`lg:block`). */
const SIDEBAR_BREAKPOINT = 1024;

function isNarrow(page: Page): boolean {
  return (page.viewportSize()?.width ?? 0) < SIDEBAR_BREAKPOINT;
}

/**
 * True when the browser had to shrink the page to fit the device.
 *
 * The liquidity header lays its four controls out in a row that needs about
 * 494 CSS px. On a Pixel 7 (412 px) the page therefore renders zoomed out, and
 * a synthetic tap no longer lands where the layout says the control is —
 * neither `click()` nor `tap()` can drive that header. An iPhone 14 (390 px)
 * wraps instead and stays drivable, so this is checked per device rather than
 * assumed per project. The underlying overflow is a Phase 0 baseline
 * observation; see `docs/ui-overhaul/device-checklist.md`.
 */
async function pageIsZoomedOut(page: Page): Promise<boolean> {
  const layoutWidth = await page.evaluate(() => window.innerWidth);
  return layoutWidth > (page.viewportSize()?.width ?? layoutWidth);
}

async function openSettingsAndSave(page: Page, settle: Settle): Promise<void> {
  await page.getByTestId('liquidity.empty.settings').click();
  await expect(page.getByTestId('settings.root')).toBeVisible();
  await page.getByTestId('settings.balance').fill('50');
  await page.getByTestId('settings.date').fill('2026-09-04');
  await page.getByTestId('settings.reserve').fill('5');
  await page.getByTestId('settings.save').click();
  await settle(TRANSITION_MS);
  await expect(page.getByTestId('settings.root')).toHaveCount(0);
}

test('the timeline loads, fails its Mercury sync, and offers the empty state', async ({
  page,
  api,
}) => {
  await page.goto('/liquidity');

  await expect(page.getByTestId('liquidity.empty')).toBeVisible();
  await expect(page.getByTestId('liquidity.toast')).toHaveText(
    `Mercury sync failed: ${MERCURY_OFFLINE_DETAIL}`,
  );

  await api.expectContract('liquidity-load');
});

test('settings, a one-off flow and a recurring series all persist', async ({
  page,
  api,
  settle,
}) => {
  await page.goto('/liquidity');
  await expect(page.getByTestId('liquidity.empty')).toBeVisible();
  test.skip(
    await pageIsZoomedOut(page),
    'the header overflows this device, so the page is zoomed out and its controls cannot be driven',
  );

  api.reset();

  await openSettingsAndSave(page, settle);
  await expect(page.getByTestId('liquidity.toast')).toHaveText('Settings saved.');
  await expect(page.getByTestId('chart.container')).toBeVisible();

  // A one-off inflow. Inflows skip the simulation warning by design — only an
  // outflow can sink the timeline.
  await page.getByTestId('liquidity.add-flow').click();
  await expect(page.getByTestId('txnform.root')).toBeVisible();
  await page.getByTestId('txnform.inflow').click();
  await page.getByTestId('txnform.amount').fill('12.5');
  await page.getByTestId('txnform.date').fill('2026-09-10');
  await page.getByTestId('txnform.description').fill('Refi proceeds');
  await page.getByTestId('txnform.save').click();
  await settle(TRANSITION_MS);
  await expect(page.getByTestId('liquidity.toast')).toHaveText('Transaction saved.');
  await expect(page.getByTestId('txnform.root')).toHaveCount(0);

  // A recurring series.
  await page.getByTestId('liquidity.add-flow').click();
  await expect(page.getByTestId('txnform.root')).toBeVisible();
  await page.getByTestId('txnform.mode-recurring').click();
  await page.getByTestId('txnform.inflow').click();
  await page.getByTestId('txnform.amount').fill('2.6');
  await page.getByTestId('txnform.start-date').fill('2026-09-05');
  await page.getByTestId('txnform.frequency').selectOption('monthly');
  await page.getByTestId('txnform.description').fill('Unit A rent');
  await page.getByTestId('txnform.save').click();
  await settle(TRANSITION_MS);
  await expect(page.getByTestId('liquidity.toast')).toHaveText(
    'Recurring series saved.',
  );
  await expect(page.getByTestId('txnform.root')).toHaveCount(0);

  await api.expectContract('liquidity-settings-and-flows');
});

test('deleting a recurring series names it in the confirm', async ({
  page,
  api,
  dialogs,
  settle,
}) => {
  test.skip(
    isNarrow(page),
    'the recurring list lives in the `lg:`-only sidebar, so there is nothing to delete from on a phone',
  );

  await page.goto('/liquidity');
  await expect(page.getByTestId('liquidity.empty')).toBeVisible();
  await openSettingsAndSave(page, settle);
  await expect(page.getByTestId('chart.container')).toBeVisible();

  await page.getByTestId('liquidity.add-flow').click();
  await page.getByTestId('txnform.mode-recurring').click();
  await page.getByTestId('txnform.inflow').click();
  await page.getByTestId('txnform.amount').fill('2.6');
  await page.getByTestId('txnform.start-date').fill('2026-09-05');
  await page.getByTestId('txnform.description').fill('Unit A rent');
  await page.getByTestId('txnform.save').click();
  await settle(TRANSITION_MS);
  await expect(page.getByTestId('liquidity.toast')).toHaveText(
    'Recurring series saved.',
  );
  await expect(page.getByTestId('txnform.root')).toHaveCount(0);

  const rule = page.locator('[data-testid^="sidebar.recurring."]').first();
  await expect(rule).toBeVisible();

  api.reset();
  dialogs.reset();

  await page
    .locator('[data-testid^="sidebar.recurring."][data-testid$=".delete"]')
    .first()
    .click();

  await dialogs.expectDialogs([
    'Delete the entire recurring series "Unit A rent"? ' +
      'This removes every projected occurrence from the timeline.',
  ]);
  await expect(page.getByTestId('liquidity.toast')).toHaveText(
    'Recurring series deleted.',
  );

  await api.expectContract('liquidity-delete-recurring');
});

test('the chart walks days with the arrow keys', async ({ page, settle }) => {
  await page.goto('/liquidity');
  await expect(page.getByTestId('liquidity.empty')).toBeVisible();
  await openSettingsAndSave(page, settle);

  const chart = page.getByTestId('chart.container');
  await expect(chart).toBeVisible();
  await expect(page.getByTestId('daydetail.root')).toHaveCount(0);

  await chart.focus();
  await chart.press('ArrowRight');

  await expect(page.getByTestId('daydetail.root')).toBeVisible();
});

test('a successful Mercury sync renders the per-workspace breakdown', async ({
  page,
}) => {
  await page.route('**/liquidity/mercury-balance', async (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(MERCURY_SUCCESS),
    }),
  );

  await page.goto('/liquidity');

  await expect(page.getByTestId('chart.container')).toBeVisible();

  const workspace = page.getByTestId('sidebar.workspace.BigWhales');
  if (isNarrow(page)) {
    // The whole sidebar is `hidden lg:block`, so on a phone the balance
    // breakdown is rendered but never shown. Baseline behaviour, recorded.
    await expect(workspace).toBeHidden();
    return;
  }

  await expect(workspace).toBeVisible();
  await expect(page.getByTestId('sidebar.account.acct-checking')).toContainText(
    'Operating',
  );
  await expect(page.getByTestId('sidebar.account.acct-reserve')).toContainText(
    '12.3k',
  );
});

/**
 * A Phase 0 baseline defect, recorded rather than fixed.
 *
 * The liquidity header lays five controls out in one unwrapped row that needs
 * more width than any phone has. The two engines cope differently — an iPhone
 * lets the row run off the right edge, a Pixel zooms the whole page out to
 * ~494 CSS px, which is what makes that header undrivable in the flow above —
 * but the underlying fact is the same on both, so that is what is asserted.
 * A later phase that makes the header fit will fail this test, which is the
 * point: the fix has to come with an updated characterization.
 */
test('the liquidity header needs more width than a phone has', async ({ page }) => {
  test.skip(!isNarrow(page), 'a desktop viewport has room to spare');

  await page.goto('/liquidity');
  await expect(page.getByTestId('liquidity.empty')).toBeVisible();

  const needed = await page.evaluate(() => {
    const ids = [
      'liquidity.back',
      'liquidity.today',
      'liquidity.mercury-sync',
      'liquidity.settings-open',
      'liquidity.add-flow',
    ];
    return Math.max(
      ...ids.map((id) => {
        const element = document.querySelector(`[data-testid="${id}"]`);
        return element ? element.getBoundingClientRect().right : 0;
      }),
    );
  });

  expect(
    needed,
    'the header row is wider than the device it is being shown on',
  ).toBeGreaterThan(page.viewportSize()!.width);
});
