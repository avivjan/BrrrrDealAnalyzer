import { expect, test } from '../fixtures';

/**
 * The deal modal's autosave, which is the single most load-bearing timing
 * behaviour in the app and the one a visual overhaul is most likely to break:
 *
 *  - a 250 ms *settle window* after opening, so the inputs mounting does not
 *    count as an edit;
 *  - a 500 ms debounce before re-analyzing;
 *  - a 2 s debounce before writing.
 *
 * The clock is frozen, so every one of those is asserted by name rather than
 * by sleeping and hoping.
 */

test('a card opens its modal on every device, including the touch board', async ({
  page,
  seed,
}) => {
  const deal = await seed.seedActiveDeal('BRRRR', { section: 1 });

  await page.goto('/my-deals');

  // On a coarse pointer `MyDeals` renders the plain grid instead of
  // `VueDraggable`; the card wrapper hook is the same either way.
  const card = page.getByTestId(`mydeals.card.${deal.id}`);
  await expect(card).toBeVisible();
  await card.click();

  await expect(page.getByTestId('mydeals.modal')).toBeVisible();
  await expect(page.getByTestId('mydeals.modal.address')).toHaveValue(deal.address);
});

test('editing after the settle window re-analyzes once, then saves once', async ({
  page,
  api,
  seed,
  settle,
}) => {
  const deal = await seed.seedActiveDeal('BRRRR', { section: 1 });

  await page.goto('/my-deals');
  await page.getByTestId(`mydeals.card.${deal.id}`).click();
  await expect(page.getByTestId('mydeals.modal')).toBeVisible();

  // Past the 250 ms settle window, and before the 500 ms analyze debounce.
  await settle(300);

  // Everything so far is arrange; the contract is what one edit costs.
  api.reset();

  await page.getByTestId('mydeals.modal.task').fill('Call the lender');
  await settle(2500);

  await expect(page.getByTestId('mydeals.modal.save-status')).toHaveAttribute(
    'data-state',
    'saved',
  );

  const put = api.matching(
    (request) => request.method === 'PUT' && request.path === '/active-deals/{id}',
  );
  expect(put).toHaveLength(1);
  expect((put[0]!.body as Record<string, unknown>).task).toBe('Call the lender');

  await api.expectContract('my-deals-autosave');
});

test('the save chip passes through saving, saved and back to idle', async ({
  page,
  seed,
  settle,
}) => {
  const deal = await seed.seedActiveDeal('BRRRR', { section: 1 });

  // Hold the PUT open so the transient `saving` state can actually be seen.
  let release!: () => void;
  const held = new Promise<void>((resolve) => {
    release = resolve;
  });
  await page.route('**/active-deals/*', async (route) => {
    if (route.request().method() !== 'PUT') return route.continue();
    await held;
    return route.continue();
  });

  await page.goto('/my-deals');
  await page.getByTestId(`mydeals.card.${deal.id}`).click();
  await expect(page.getByTestId('mydeals.modal')).toBeVisible();
  await settle(300);

  const chip = page.getByTestId('mydeals.modal.save-status');
  await expect(chip).toHaveAttribute('data-state', 'idle');

  await page.getByTestId('mydeals.modal.task').fill('Order the appraisal');
  await settle(2500);
  await expect(chip).toHaveAttribute('data-state', 'saving');

  release();
  await expect(chip).toHaveAttribute('data-state', 'saved');

  // The chip clears itself two seconds later.
  await settle(2100);
  await expect(chip).toHaveAttribute('data-state', 'idle');
});

test('an edit inside the settle window is not treated as an edit', async ({
  page,
  api,
  seed,
  settle,
}) => {
  const deal = await seed.seedActiveDeal('BRRRR', { section: 1 });

  await page.goto('/my-deals');
  await page.getByTestId(`mydeals.card.${deal.id}`).click();
  await expect(page.getByTestId('mydeals.modal')).toBeVisible();

  api.reset();

  // No `settle` first: still inside the 250 ms window opened by `openDeal`.
  await page.getByTestId('mydeals.modal.task').fill('Typed too early');
  await settle(2500);

  expect(
    api.matching((request) => request.method === 'PUT'),
    'an edit inside the settle window must not persist',
  ).toEqual([]);
  await expect(page.getByTestId('mydeals.modal.save-status')).toHaveAttribute(
    'data-state',
    'idle',
  );
});
