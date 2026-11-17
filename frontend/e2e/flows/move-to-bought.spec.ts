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
  settle,
}) => {
  const deal = await seed.seedActiveDeal('BRRRR', { section: 1, stage: 3 });

  await page.goto('/my-deals');
  const card = page.getByTestId(`mydeals.card.${deal.id}`);
  await expect(card).toBeVisible();
  await expect(page.getByTestId('mydeals.stage.3')).toContainText(deal.address);

  api.reset();

  await card.getByTestId('dealcard.move-to-bought').click();

  // It asks for the deal's own Google Drive folder (tasks/todo/DealDriveFolderRehabSummaryAndProjection.md) and refuses
  // anything but a Drive folder link.
  const moveDialog = page.getByTestId('move-to-bought.root');
  await expect(moveDialog).toBeVisible();
  await page.getByTestId('move-to-bought.confirm').click();
  await expect(page.getByTestId('move-to-bought.link-problem')).toContainText('Paste');
  await page.getByTestId('move-to-bought.google-drive-link').fill('https://docs.google.com/document/d/1AbCdEfGhIjKlMnOp/edit');
  await page.getByTestId('move-to-bought.confirm').click();
  await expect(page.getByTestId('move-to-bought.link-problem')).toContainText('not a Google Drive folder link');
  expect(await seed.listBoughtDeals()).toHaveLength(0);
  await page.getByTestId('move-to-bought.google-drive-link').fill('https://drive.google.com/drive/folders/E2EDealFolder0001');
  await page.getByTestId('move-to-bought.confirm').click();

  await dialogs.expectDialogs(['Deal moved to Bought Deals successfully!']);
  await expect.poll(async () => { await settle(400); return moveDialog.count(); }).toBe(0);   // it leaves on the paused clock

  // Today's behaviour: the active card is not removed.
  await expect(card).toBeVisible();

  const [boughtDeal] = await seed.listBoughtDeals();
  expect(boughtDeal?.google_drive_link).toBe('https://drive.google.com/drive/folders/E2EDealFolder0001');

  await api.expectContract('move-to-bought');
});

test('HTML to Drive saves the deal projection in the deal\'s Drive folder, and says where', async ({ page, request, seed, settle }) => {
  const { API_ORIGIN } = await import('../fixtures/env');
  const deal = await seed.seedBoughtDeal('BRRRR');
  const callsBefore = await (await request.get(`${API_ORIGIN}/e2e/fake-mercury/calls`, { headers: { 'x-e2e-seed': '1' } })).json();

  await page.goto('/bought-deals');
  await page.getByTestId(`boughtdeals.card.${deal.id}`).click();
  await expect(page.getByTestId('boughtdeals.modal')).toBeVisible();
  await settle(300);
  await page.getByTestId('boughtdeals.modal.html-to-drive').click();

  await expect(page.getByTestId('boughtdeals.modal.html-to-drive.saved')).toContainText(/\d{4}-\d{2}-\d{2} deal projection\.html/);
  const callsAfter = await (await request.get(`${API_ORIGIN}/e2e/fake-mercury/calls`, { headers: { 'x-e2e-seed': '1' } })).json();
  expect(callsAfter.deal_projection_files_saved_to_drive - callsBefore.deal_projection_files_saved_to_drive).toBe(1);
});
