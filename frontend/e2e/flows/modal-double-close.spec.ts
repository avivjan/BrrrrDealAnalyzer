import { expect, test } from '../fixtures';

/**
 * Closing a dirty deal modal twice in a row.
 *
 * `closeModal` flushes the pending save before it hides the modal, and it is
 * `async` — so a second click that lands before the first `await` resolves is
 * a second flush of the same edit. Today `performSave` guards that with its
 * `isDirty` flag; this is the test that says so out loud, because a restyle
 * that adds a transition to the close button is exactly what re-opens the gap.
 */

test('two Close clicks in the same tick still write once', async ({
  page,
  api,
  seed,
  settle,
}) => {
  const deal = await seed.seedActiveDeal('BRRRR', { section: 1 });

  await page.goto('/my-deals');
  await page.getByTestId(`mydeals.card.${deal.id}`).click();
  await expect(page.getByTestId('mydeals.modal')).toBeVisible();
  await settle(300);

  api.reset();

  await page.getByTestId('mydeals.modal.task').fill('Chase the title company');
  await settle(100);

  // Both clicks in one tick, from inside the page: two Playwright `click()`
  // calls are two round-trips apart, which is long enough for `closeModal` to
  // finish and hide the modal — so the second one never races the first and
  // the test proves nothing. This is the real double-tap.
  await expect(page.getByTestId('mydeals.modal.footer-close')).toBeVisible();
  await page.evaluate(() => {
    const close = document.querySelector<HTMLElement>(
      '[data-testid="mydeals.modal.footer-close"]',
    );
    close?.click();
    close?.click();
  });

  await expect(page.getByTestId('mydeals.modal')).toHaveCount(0);

  await expect
    .poll(() => api.matching((request) => request.method === 'PUT').length)
    .toBe(1);
  await api.expectContract('modal-double-close');
});
