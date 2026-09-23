import { expect, test } from '../fixtures';
import { fieldInput, openTabOf } from '../fixtures/form';

/**
 * Typing into a money field the way a person does: click the box and type,
 * with no select-all first.
 *
 * `MoneyInput` selects its whole value on focus so the typed number replaces
 * it. That selection used to be made before the focus re-render swapped the
 * formatted "$288,000" for the editable "288000", which collapsed it, so the
 * typed digits were appended: a lowest ARV of $288,000,250,000, rejected by
 * both analyze and save ("Lowest ARV cannot exceed ARV"), so the results never
 * moved and reopening the deal showed the old value.
 */

async function openBoughtDealModal(page: import('@playwright/test').Page, dealId: string, settle: (ms: number) => Promise<void>) {
  await page.goto('/bought-deals');
  await page.getByTestId(`boughtdeals.card.${dealId}`).click();
  await expect(page.getByTestId('boughtdeals.modal')).toBeVisible();
  await settle(400);
}

test('typing a lowest ARV replaces the shown value, re-analyzes, saves and survives a reopen', async ({
  page,
  api,
  seed,
  settle,
}) => {
  const deal = await seed.seedBoughtDeal('BRRRR');
  await openBoughtDealModal(page, deal.id, settle);
  await openTabOf(page, 'lowestArv');
  const lowestArvInput = fieldInput(page, 'lowestArv');
  const conservativeWireTile = page.getByTestId('boughtdeals.modal.result.cash_out_routi_conservative');
  const conservativeWireBeforeTyping = await conservativeWireTile.innerText();

  api.reset();
  await lowestArvInput.click();
  await page.keyboard.type('250000');
  await lowestArvInput.blur();
  await settle(2500);

  await expect(lowestArvInput).toHaveValue('$250,000');
  await expect(page.getByTestId('boughtdeals.modal.save-status')).toHaveAttribute('data-state', 'saved');
  const savePuts = api.matching((request) => request.method === 'PUT' && request.path === '/bought-deals/{id}');
  expect(savePuts).toHaveLength(1);
  expect((savePuts[0]!.body as Record<string, unknown>).lowestArv).toBe(250);
  await expect(conservativeWireTile).not.toHaveText(conservativeWireBeforeTyping);

  await page.getByTestId('boughtdeals.modal.close').click();
  await expect(page.getByTestId('boughtdeals.modal')).toHaveCount(0);
  await openBoughtDealModal(page, deal.id, settle);
  await openTabOf(page, 'lowestArv');
  await expect(fieldInput(page, 'lowestArv')).toHaveValue('$250,000');
});

test('clicking into a formula-default money field and leaving keeps it on the formula', async ({
  page,
  api,
  seed,
  settle,
}) => {
  const deal = await seed.seedBoughtDeal('BRRRR');
  await openBoughtDealModal(page, deal.id, settle);

  api.reset();
  for (const formulaDefaultFieldName of ['recordingTransferBuy', 'titleEscrowBuy', 'vacancyReserve', 'lowestArv']) {
    await openTabOf(page, formulaDefaultFieldName);
    const formulaDefaultInput = fieldInput(page, formulaDefaultFieldName);
    await formulaDefaultInput.click();
    await formulaDefaultInput.blur();
    await expect(page.getByTestId(`form.field.${formulaDefaultFieldName}`)).toHaveAttribute('data-auto', 'true');
  }
  await settle(2500);

  expect(api.matching((request) => request.method === 'PUT' && request.path === '/bought-deals/{id}')).toHaveLength(0);
});
