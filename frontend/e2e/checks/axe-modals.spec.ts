import {
  BRRRR_FORM_FIELDS,
  BRRRR_PAYLOAD,
  checkA11y,
  expect,
  fillForm,
  test,
} from '../fixtures';

/**
 * Axe on the states the route-level baseline never sees.
 *
 * `flows/a11y.spec.ts` scans six routes, on chromium, at one desktop width, on
 * an empty database, with nothing open. That hides two whole classes of
 * defect: everything inside an overlay (the deal modals, the save modal, the
 * liquidity forms), and everything a narrow viewport changes (icon-only
 * controls that lose their text, layouts that stack). Both were found by hand
 * in v1's quality snapshot and could not be held to a baseline. This spec
 * gives each such state its own baseline key, recorded with `npm run
 * e2e:record` and then held to "no new rule, no higher count" like any route.
 *
 * Seeded boards are scanned too: a card's substage checkboxes only exist once
 * a deal does, and the empty-board baseline never met them.
 *
 * `checkA11y` resumes the fake clock and must stay the last step of a test.
 */

test.beforeEach(({}, testInfo) => {
  test.skip(
    testInfo.project.name !== 'chromium',
    'the axe baseline is recorded and replayed on chromium only',
  );
});

test.describe('overlays and seeded boards (desktop)', () => {
  test('the My Deals board with a deal, then its modal', async ({ page, seed }) => {
    const deal = await seed.seedActiveDeal('BRRRR', { section: 1 });
    await page.goto('/my-deals');
    const card = page.getByTestId(`mydeals.card.${deal.id}`);
    await expect(card).toBeVisible();
    await checkA11y(page, 'my-deals@seeded');

    await card.click();
    await expect(page.getByTestId('mydeals.modal')).toBeVisible();
    await checkA11y(page, 'my-deals@modal');
  });

  test('the Bought Deals board with a deal, then its modal', async ({ page, seed }) => {
    const deal = await seed.seedBoughtDeal('BRRRR');
    await page.goto('/bought-deals');
    const card = page.getByTestId(`boughtdeals.card.${deal.id}`);
    await expect(card).toBeVisible();
    await checkA11y(page, 'bought-deals@seeded');

    await card.click();
    await expect(page.getByTestId('boughtdeals.modal')).toBeVisible();
    await checkA11y(page, 'bought-deals@modal');
  });

  test('the Analyze save modal', async ({ page }) => {
    await page.goto('/analyze');
    await expect(page.getByTestId('form.root')).toBeVisible();
    await fillForm(page, BRRRR_FORM_FIELDS, BRRRR_PAYLOAD);
    await page.getByTestId('analyze.analyze-save').click();
    await expect(page.getByTestId('analyze.modal')).toBeVisible();
    await checkA11y(page, 'analyze@save-modal');
  });

  test('the liquidity transaction form', async ({ page }) => {
    await page.goto('/liquidity');
    await page.getByTestId('liquidity.add-flow').click();
    await expect(page.getByTestId('txnform.root')).toBeVisible();
    await checkA11y(page, 'liquidity@txnform');
  });

  test('the liquidity settings panel', async ({ page }) => {
    await page.goto('/liquidity');
    await page.getByTestId('liquidity.settings-open').click();
    await expect(page.getByTestId('settings.root')).toBeVisible();
    await checkA11y(page, 'liquidity@settings');
  });
});

/** The same six routes as `flows/a11y.spec.ts`, at a phone width. */
const ROUTES: [name: string, path: string, ready: string][] = [
  ['landing', '/', 'landing.offer'],
  ['analyze', '/analyze', 'form.root'],
  ['my-deals', '/my-deals', 'mydeals.add-deal'],
  ['bought-deals', '/bought-deals', 'boughtdeals.edit-pipeline'],
  ['liquidity', '/liquidity', 'liquidity.add-flow'],
  ['reps', '/reps', 'reps.manual-entry'],
];

test.describe('every route at 390px', () => {
  test.use({ viewport: { width: 390, height: 844 } });

  for (const [name, path, ready] of ROUTES) {
    test(`${name} at 390px has no accessibility violations outside the baseline`, async ({
      page,
    }) => {
      await page.goto(path);
      await expect(page.getByTestId(ready)).toBeVisible();
      await checkA11y(page, `${name}@390`);
    });
  }
});
