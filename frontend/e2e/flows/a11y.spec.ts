import { checkA11y, expect, test } from '../fixtures';

/**
 * The accessibility baseline for all six routes.
 *
 * Phase 0 fixes nothing — it writes down exactly what axe finds today so a
 * later phase can be held to "no new violations". Recorded and replayed on
 * chromium only: axe's rules are engine-independent, and running four copies
 * of the same scan would only make the suite slower and the baseline harder to
 * read.
 */

const ROUTES: [name: string, path: string, ready: string][] = [
  ['landing', '/', 'landing.offer'],
  ['analyze', '/analyze', 'form.root'],
  ['my-deals', '/my-deals', 'mydeals.add-deal'],
  ['bought-deals', '/bought-deals', 'boughtdeals.edit-pipeline'],
  ['liquidity', '/liquidity', 'liquidity.add-flow'],
  ['reps', '/reps', 'reps.manual-entry'],
];

test.beforeEach(({}, testInfo) => {
  test.skip(
    testInfo.project.name !== 'chromium',
    'the axe baseline is recorded and replayed on chromium only',
  );
});

for (const [name, path, ready] of ROUTES) {
  test(`${name} has no accessibility violations outside the baseline`, async ({
    page,
  }) => {
    await page.goto(path);
    await expect(page.getByTestId(ready)).toBeVisible();
    await checkA11y(page, name);
  });
}
