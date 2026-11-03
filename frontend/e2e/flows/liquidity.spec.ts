import { expect, test } from '../fixtures';

/**
 * The liquidity timeline, which is the theater page (tasks/todo/LiquidityTheaterOnly.md).
 *
 * Four requests on load, a Mercury sync that this environment always refuses,
 * settings from the action bar, and then the two ways money enters the timeline
 * (a one-off and a recurring series). The chart's keyboard contract — the arrow
 * keys walk days, Enter opens the day — is the only way a keyboard user reaches
 * the data at all, and it is asserted here rather than assumed.
 */

const MERCURY_OFFLINE_DETAIL =
  'No Mercury tokens found. Add MERCURY_API_TOKEN_<LABEL> entries ' +
  '(e.g. MERCURY_API_TOKEN_AJYK, MERCURY_API_TOKEN_AY) to BackEnd/.env.';

const MERCURY_SUCCESS = {
  total_balance_dollars: 61500,
  total_available_dollars: 61500,
  account_count: 2,
  workspace_count: 1,
  workspaces: [
    {
      workspace: 'BigWhales',
      total_balance_dollars: 61500,
      total_available_dollars: 61500,
      account_count: 2,
      accounts: [
        {
          id: 'acct-checking',
          name: 'Operating',
          type: 'checking',
          status: 'active',
          current_balance_dollars: 49200,
          available_balance_dollars: 49200,
          workspace: 'BigWhales',
          is_counted_as_cash: true,
        },
        {
          id: 'acct-reserve',
          name: 'Reserve',
          type: 'savings',
          status: 'active',
          current_balance_dollars: 12300,
          available_balance_dollars: 12300,
          workspace: 'BigWhales',
          is_counted_as_cash: true,
        },
      ],
    },
  ],
  workspace_errors: [],
  accounts: [],
  counted_as_cash_balance_dollars: 61500,
  mercury_account_ids_counted_as_cash: null,
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

/**
 * An action of the theater's action bar: on a phone the secondary ones
 * (Today, Mercury, Settings) sit behind the ⋯ menu.
 */
async function clickTheaterAction(page: Page, action: 'settings' | 'mercury-sync' | 'today'): Promise<void> {
  const button = page.getByTestId(`theater.${action}`);
  if (await button.isVisible()) {
    await button.click();
    return;
  }
  await page.getByTestId('theater.more').click();
  await page.getByTestId(`theater.more.${action}`).click();
}

/**
 * The theater shows from the first render, before the data arrives: wait for the load and the (refused) Mercury
 * sync to finish, so a recorder reset after this sees only the requests the test makes.
 */
async function waitForTheFirstLoad(page: Page): Promise<void> {
  await expect(page.getByTestId('theater.root')).toBeVisible();
  await expect(page.getByTestId('liquidity.loading')).toHaveCount(0);
  await expect(page.getByTestId('liquidity.toast')).toHaveText(`Mercury sync failed: ${MERCURY_OFFLINE_DETAIL}`);
}

async function openSettingsAndSave(page: Page, settle: Settle): Promise<void> {
  await clickTheaterAction(page, 'settings');
  await expect(page.getByTestId('settings.root')).toBeVisible();
  await page.getByTestId('settings.balance').fill('50000');
  await page.getByTestId('settings.date').fill('2026-09-04');
  await page.getByTestId('settings.reserve').fill('5000');
  await page.getByTestId('settings.save').click();
  await settle(TRANSITION_MS);
  await expect(page.getByTestId('settings.root')).toHaveCount(0);
}

async function openLegend(page: Page, settle: Settle) {
  const legendToggle = page.getByTestId('theater.legend-toggle');
  await expect(legendToggle).toBeVisible();
  if ((await legendToggle.getAttribute('aria-expanded')) !== 'true') await legendToggle.click();
  await settle(TRANSITION_MS);
  const legend = page.getByTestId('theater.legend');
  await expect(legend).toBeVisible();
  return legend;
}

test('the timeline loads straight into the theater and fails its Mercury sync', async ({
  page,
  api,
}) => {
  await page.goto('/liquidity');

  await expect(page.getByTestId('theater.root')).toBeVisible();
  await expect(page.getByTestId('chart.container')).toBeVisible();
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
  await waitForTheFirstLoad(page);

  api.reset();

  await openSettingsAndSave(page, settle);
  await expect(page.getByTestId('liquidity.toast')).toHaveText('Settings saved.');
  await expect(page.getByTestId('chart.container')).toBeVisible();

  // A one-off inflow. Inflows skip the simulation warning by design — only an
  // outflow can sink the timeline.
  await page.getByTestId('theater.add-flow').click();
  await expect(page.getByTestId('txnform.root')).toBeVisible();
  await page.getByTestId('txnform.inflow').click();
  await page.getByTestId('txnform.amount').fill('12500');
  await page.getByTestId('txnform.date').fill('2026-09-10');
  await page.getByTestId('txnform.description').fill('Refi proceeds');
  await page.getByTestId('txnform.save').click();
  await settle(TRANSITION_MS);
  await expect(page.getByTestId('liquidity.toast')).toHaveText('Transaction saved.');
  await expect(page.getByTestId('txnform.root')).toHaveCount(0);

  // A recurring series.
  await page.getByTestId('theater.add-flow').click();
  await expect(page.getByTestId('txnform.root')).toBeVisible();
  await page.getByTestId('txnform.mode-recurring').click();
  await page.getByTestId('txnform.inflow').click();
  await page.getByTestId('txnform.amount').fill('2600');
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
  await page.goto('/liquidity');
  await waitForTheFirstLoad(page);
  await openSettingsAndSave(page, settle);
  await expect(page.getByTestId('chart.container')).toBeVisible();

  await page.getByTestId('theater.add-flow').click();
  await page.getByTestId('txnform.mode-recurring').click();
  await page.getByTestId('txnform.inflow').click();
  await page.getByTestId('txnform.amount').fill('2600');
  await page.getByTestId('txnform.start-date').fill('2026-09-05');
  await page.getByTestId('txnform.description').fill('Unit A rent');
  await page.getByTestId('txnform.save').click();
  await settle(TRANSITION_MS);
  await expect(page.getByTestId('liquidity.toast')).toHaveText(
    'Recurring series saved.',
  );
  await expect(page.getByTestId('txnform.root')).toHaveCount(0);

  const legend = await openLegend(page, settle);
  const rule = legend.locator('[data-testid^="theater.legend.recurring."]').first();
  await expect(rule).toBeVisible();

  api.reset();
  dialogs.reset();

  await legend
    .locator('[data-testid^="theater.legend.recurring."][data-testid$=".delete"]')
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

test('the chart walks days with the arrow keys, and Enter opens the day', async ({ page, settle }) => {
  await page.goto('/liquidity');
  await waitForTheFirstLoad(page);
  await openSettingsAndSave(page, settle);

  const chart = page.getByTestId('chart.container');
  await expect(chart).toBeVisible();
  await expect(page.getByTestId('theater.day-modal')).toHaveCount(0);

  await chart.focus();
  await chart.press('ArrowRight');
  // The arrow keys preview the day; they do not open it.
  await expect(page.getByTestId('chart.tooltip')).toBeVisible();
  await expect(page.getByTestId('theater.day-modal')).toHaveCount(0);

  await chart.press('Enter');
  await expect(page.getByTestId('theater.day-modal')).toBeVisible();
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

  await page.getByTestId('theater.figure.balance').click();
  const popover = page.getByTestId('theater.balance-popover');
  await expect(popover.getByTestId('theater.balance-popover.workspace.BigWhales')).toBeVisible();
  await expect(popover.getByTestId('theater.balance-popover.account.acct-checking')).toContainText('Operating');
  await expect(popover.getByTestId('theater.balance-popover.account.acct-reserve')).toContainText('$12,300');
  await expect(popover.getByTestId('theater.balance-popover.sync')).toContainText('2 accounts across 1 workspace');
});
