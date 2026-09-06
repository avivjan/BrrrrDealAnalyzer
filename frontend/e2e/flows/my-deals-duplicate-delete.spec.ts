import { expect, test } from '../fixtures';

/**
 * Duplicate and delete, from the card and from the modal.
 *
 * Both are guarded by a native `confirm`, and the wording of those four
 * strings is user-visible behaviour: they are asserted verbatim here so a
 * later phase cannot quietly reword "are you sure you want to delete 12 Main
 * St?" into something that no longer names the property.
 */

test('the card duplicates and deletes behind their confirms', async ({
  page,
  api,
  dialogs,
  seed,
}) => {
  const deal = await seed.seedActiveDeal('BRRRR', { section: 1 });

  await page.goto('/my-deals');
  const card = page.getByTestId(`mydeals.card.${deal.id}`);
  await expect(card).toBeVisible();

  api.reset();

  await card.getByTestId('dealcard.duplicate').click();
  await expect
    .poll(() => api.matching((request) => request.method === 'POST').length)
    .toBe(1);

  await card.getByTestId('dealcard.delete').click();
  await expect(card).toHaveCount(0);

  await dialogs.expectDialogs([
    'Are you sure you want to duplicate this deal?',
    `Are you sure you want to delete ${deal.address}?`,
  ]);

  await api.expectContract('my-deals-card-duplicate-delete');
});

test('the modal duplicates and deletes behind their confirms', async ({
  page,
  api,
  dialogs,
  seed,
}) => {
  const deal = await seed.seedActiveDeal('BRRRR', { section: 1 });

  await page.goto('/my-deals');
  await page.getByTestId(`mydeals.card.${deal.id}`).click();
  await expect(page.getByTestId('mydeals.modal')).toBeVisible();

  api.reset();

  await page.getByTestId('mydeals.modal.duplicate').click();
  await expect(page.getByTestId('mydeals.modal')).toHaveCount(0);

  // Re-open the original and delete it from inside.
  await page.getByTestId(`mydeals.card.${deal.id}`).click();
  await expect(page.getByTestId('mydeals.modal')).toBeVisible();
  await page.getByTestId('mydeals.modal.delete').click();
  await expect(page.getByTestId('mydeals.modal')).toHaveCount(0);
  await expect(page.getByTestId(`mydeals.card.${deal.id}`)).toHaveCount(0);

  await dialogs.expectDialogs([
    'Duplicate this deal?',
    `Are you sure you want to delete ${deal.address}?`,
  ]);

  await api.expectContract('my-deals-modal-duplicate-delete');
});
