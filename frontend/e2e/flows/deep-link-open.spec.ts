import {
  expect,
  expectNoLiveTweens,
  expectOverlayFillsViewport,
  test,
} from '../fixtures';

/**
 * The deep link that every save redirects through: `/my-deals?openDeal=…`.
 *
 * Three separate promises live in that one URL — the right tab is selected,
 * the modal opens on the right deal, and the query is scrubbed so a refresh or
 * a back button doesn't re-open it. All three are asserted here.
 *
 * Tagged `@motion` so it also runs with animations *on*: the deal modal is a
 * full-viewport overlay, and an entrance animation that starts it scaled down
 * leaves a live gap around the edges where a tap goes to the board behind it.
 */

test('a deep link opens the deal, clears the query and covers the viewport @motion', async ({
  page,
  api,
  seed,
  settle,
}) => {
  const deal = await seed.seedActiveDeal('BRRRR', { section: 2 });

  await page.goto(
    `/my-deals?openDeal=${deal.id}&dealType=BRRRR&section=${deal.section}`,
  );

  const modal = page.getByTestId('mydeals.modal');
  await expect(modal).toBeVisible();
  await expect(page.getByTestId('mydeals.modal.address')).toHaveValue(deal.address);
  await expect(page.getByTestId('mydeals.modal.results')).toBeVisible();

  // The section from the query picked the tab the deal actually lives on.
  await expect(page.getByTestId(`mydeals.card.${deal.id}`)).toHaveCount(1);

  await expect.poll(() => new URL(page.url()).search).toBe('');
  await expect.poll(() => new URL(page.url()).pathname).toBe('/my-deals');

  await expectOverlayFillsViewport(page, 'mydeals.modal');
  await expectNoLiveTweens(page);

  await settle(600);
  await api.expectContract('deep-link-open');
});
