import { expect, test } from '../fixtures';

/**
 * The Bought Deals modal. Same autosave machinery as My Deals, driven by two
 * things unique to this board: the per-stage substage checklist, and the
 * pipeline-stage `<select>`. Ticking a box is an edit like any other — it does
 * not write immediately, it joins the 2 s debounce — and that is worth
 * freezing, because "did my checkbox save?" is exactly the kind of thing a
 * restyle breaks silently.
 */

const PURCHASE_SUBSTAGES = ['purchase_agreement', 'emd'];

test('the board loads its deals and its pipeline templates', async ({
  page,
  api,
  seed,
}) => {
  const deal = await seed.seedBoughtDeal('BRRRR');

  await page.goto('/bought-deals');
  await expect(page.getByTestId(`boughtdeals.card.${deal.id}`)).toBeVisible();
  await expect(page.getByTestId('boughtdeals.stage.purchase')).toContainText(
    deal.address,
  );

  await api.expectContract('bought-deals-load');
});

test('ticking a substage re-analyzes and autosaves', async ({
  page,
  api,
  seed,
  settle,
}) => {
  const deal = await seed.seedBoughtDeal('BRRRR');

  await page.goto('/bought-deals');
  await page.getByTestId(`boughtdeals.card.${deal.id}`).click();
  await expect(page.getByTestId('boughtdeals.modal')).toBeVisible();
  await settle(300);

  api.reset();

  await page
    .getByTestId(`boughtdeals.modal.substage.${PURCHASE_SUBSTAGES[0]}.input`)
    .click();
  await settle(2500);

  await expect(page.getByTestId('boughtdeals.modal.save-status')).toHaveAttribute(
    'data-state',
    'saved',
  );

  const put = api.matching(
    (request) => request.method === 'PUT' && request.path === '/bought-deals/{id}',
  );
  expect(put).toHaveLength(1);
  expect(
    (put[0]!.body as Record<string, Record<string, boolean>>).completedSubstages,
  ).toEqual({ [PURCHASE_SUBSTAGES[0]!]: true });

  await api.expectContract('bought-deals-substage-autosave');
});

test('completing every substage reveals Advance', async ({
  page,
  seed,
  settle,
}) => {
  const deal = await seed.seedBoughtDeal('BRRRR');

  await page.goto('/bought-deals');
  await page.getByTestId(`boughtdeals.card.${deal.id}`).click();
  await expect(page.getByTestId('boughtdeals.modal')).toBeVisible();
  await settle(300);

  await expect(page.getByTestId('boughtdeals.modal.advance')).toHaveCount(0);

  for (const substage of PURCHASE_SUBSTAGES) {
    await page.getByTestId(`boughtdeals.modal.substage.${substage}.input`).click();
  }

  await expect(page.getByTestId('boughtdeals.modal.advance')).toBeVisible();
  await settle(2500);
});

test('changing the pipeline stage from the select autosaves', async ({
  page,
  api,
  seed,
  settle,
}) => {
  const deal = await seed.seedBoughtDeal('BRRRR');

  await page.goto('/bought-deals');
  await page.getByTestId(`boughtdeals.card.${deal.id}`).click();
  await expect(page.getByTestId('boughtdeals.modal')).toBeVisible();
  await settle(300);

  api.reset();

  await page
    .getByTestId('boughtdeals.modal.stage-select')
    .selectOption('prepare_for_closing');
  await settle(2500);

  const put = api.matching(
    (request) => request.method === 'PUT' && request.path === '/bought-deals/{id}',
  );
  expect(put).toHaveLength(1);
  expect((put[0]!.body as Record<string, unknown>).boughtStage).toBe(
    'prepare_for_closing',
  );

  await api.expectContract('bought-deals-stage-select');
});
