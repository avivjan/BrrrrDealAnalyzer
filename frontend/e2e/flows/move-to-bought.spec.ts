import { expect, test } from '../fixtures';

/**
 * Promoting a deal into the bought pipeline.
 *
 * Today this *copies* rather than moves: the card stays on the My Deals board
 * afterwards. That is very likely a bug, and it is exactly why it is written
 * down here — Phase 0 freezes what the app does, so a later phase that changes
 * it has to change this file too, deliberately.
 */

test('a stage-3 card copies itself into Bought Deals and stays put', async ({
  page,
  api,
  dialogs,
  seed,
}) => {
  const deal = await seed.seedActiveDeal('BRRRR', { section: 1, stage: 3 });

  await page.goto('/my-deals');
  const card = page.getByTestId(`mydeals.card.${deal.id}`);
  await expect(card).toBeVisible();
  await expect(page.getByTestId('mydeals.stage.3')).toContainText(deal.address);

  api.reset();

  await card.getByTestId('dealcard.move-to-bought').click();

  await dialogs.expectDialogs([
    'Move this deal to Bought Deals? A copy will be created in the Bought Deals pipeline.',
    'Deal moved to Bought Deals successfully!',
  ]);

  // Today's behaviour: the active card is not removed.
  await expect(card).toBeVisible();

  expect(await seed.listBoughtDeals()).toHaveLength(1);

  await api.expectContract('move-to-bought');
});
