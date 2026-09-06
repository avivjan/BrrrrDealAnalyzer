import { expect, test } from '../fixtures';

/**
 * The pipeline template editor.
 *
 * Opening it fans out three requests — the templates plus a usage-stats call
 * per deal type — and saving writes the whole stage array back. Stage and
 * substage IDs are stable by design (a rename must never orphan a deal), so
 * the saved body is the thing worth freezing, not the labels.
 */

test('opening the editor loads the templates and both stats', async ({
  page,
  api,
  seed,
}) => {
  await seed.seedBoughtDeal('BRRRR');

  await page.goto('/bought-deals');
  await expect(page.getByTestId('boughtdeals.edit-pipeline')).toBeVisible();

  api.reset();

  await page.getByTestId('boughtdeals.edit-pipeline').click();
  await expect(page.getByTestId('pipeline.root')).toBeVisible();
  await expect(page.getByTestId('pipeline.stage.0.name')).toHaveValue('Purchase');

  await api.expectContract('pipeline-editor-open');
});

test('renaming a stage and adding a substage saves the whole template', async ({
  page,
  api,
  seed,
}) => {
  await seed.seedBoughtDeal('BRRRR');

  await page.goto('/bought-deals');
  await page.getByTestId('boughtdeals.edit-pipeline').click();
  await expect(page.getByTestId('pipeline.root')).toBeVisible();

  await page.getByTestId('pipeline.stage.0.name').fill('Under Contract');
  await page.getByTestId('pipeline.stage.0.add-substage').click();

  api.reset();

  await page.getByTestId('pipeline.save').click();
  await expect(page.getByTestId('pipeline.root')).toHaveCount(0);

  const put = api.matching(
    (request) =>
      request.method === 'PUT' && request.path === '/pipeline-templates/BRRRR',
  );
  expect(put).toHaveLength(1);
  const sent = (put[0]!.body as { stages: { name: string; subStages: unknown[] }[] }).stages;
  expect(sent[0]!.name).toBe('Under Contract');
  expect(sent[0]!.subStages).toHaveLength(3);

  // Stage ids are redacted in the golden (they share a key name with the
  // volatile uuids everywhere else), so the "a rename never moves an id"
  // guarantee is checked against what the server actually stored.
  const [brrr] = (await seed.listPipelineTemplates()).filter(
    (row) => row.dealType === 'BRRRR',
  );
  expect(brrr!.stages[0]!.id).toBe('purchase');
  expect(brrr!.stages[0]!.name).toBe('Under Contract');
  expect(brrr!.stages[0]!.subStages.map((sub) => sub.id).slice(0, 2)).toEqual([
    'purchase_agreement',
    'emd',
  ]);

  await api.expectContract('pipeline-editor-save');
});

test('removing a stage names it, and its deal count, in the confirm', async ({
  page,
  api,
  dialogs,
  seed,
}) => {
  await seed.seedBoughtDeal('BRRRR');

  await page.goto('/bought-deals');
  await page.getByTestId('boughtdeals.edit-pipeline').click();
  await expect(page.getByTestId('pipeline.root')).toBeVisible();
  // Stats have to have landed for the count in the message to be right.
  await expect(page.getByTestId('pipeline.stage.6.name')).toBeVisible();

  api.reset();

  // Stage 0 is `purchase`, where the seeded deal sits.
  dialogs.setAccept(false);
  await page.getByTestId('pipeline.stage.0.delete').click();
  await dialogs.expectDialogs([
    'Delete stage "Purchase"? 1 deal(s) are currently on this stage and will be clamped to the nearest remaining stage.',
  ]);
  await expect(page.getByTestId('pipeline.stage.0.name')).toHaveValue('Purchase');

  // A stage nobody is standing on gets the short version.
  dialogs.reset();
  dialogs.setAccept(false);
  await page.getByTestId('pipeline.stage.3.delete').click();
  await dialogs.expectDialogs(['Delete stage "Rehab"?']);

  await api.expectNoRequests('declining a stage deletion must not save');
});
