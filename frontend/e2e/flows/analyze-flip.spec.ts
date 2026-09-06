import {
  FLIP_FORM_FIELDS,
  FLIP_PAYLOAD,
  expect,
  fillForm,
  test,
} from '../fixtures';

/**
 * The FLIP twin of `analyze-brrr`. The one behaviour unique to this path is
 * the sale-price / ARV mirror: `AnalyzeDeal.vue` watches both and copies one
 * into the other, so typing a sale price is enough and `arv_in_thousands`
 * must arrive at the server carrying the same number.
 */

const RESULT_KEYS = [
  'net_profit',
  'roi',
  'annualized_roi',
  'total_cash_needed',
  'total_cash_needed_with_buffer',
  'total_holding_costs',
  'total_hml_interest',
];

test('analyze a FLIP deal, save it, and land on its open modal', async ({
  page,
  api,
  settle,
}) => {
  await page.goto('/analyze');
  await page.getByTestId('analyze.type-flip').click();
  await expect(page.getByTestId('form.field.salePrice')).toBeVisible();

  await fillForm(page, FLIP_FORM_FIELDS, FLIP_PAYLOAD);

  await page.getByTestId('analyze.analyze-save').click();
  await expect(page.getByTestId('analyze.modal')).toBeVisible();

  await page.getByTestId('analyze.modal.address').fill(FLIP_PAYLOAD.address);
  await page
    .getByTestId('analyze.modal.section')
    .selectOption(String(FLIP_PAYLOAD.section));
  await page
    .getByTestId('analyze.modal.stage')
    .selectOption(String(FLIP_PAYLOAD.stage));

  await page.getByTestId('analyze.modal.save').click();

  await expect(page.getByTestId('mydeals.modal')).toBeVisible();
  await expect.poll(() => new URL(page.url()).search).toBe('');

  await settle(600);
  await expect(page.getByTestId('mydeals.modal.results')).toBeVisible();

  const rendered: Record<string, string> = {};
  for (const key of RESULT_KEYS) {
    rendered[key] = (
      await page.getByTestId(`mydeals.modal.result.${key}`).innerText()
    ).trim();
  }

  const saved = api.matching(
    (request) => request.method === 'POST' && request.path === '/active-deals',
  );
  expect(saved).toHaveLength(1);

  // Only the fields a FLIP form actually renders. The BRRRR-only inputs (rent,
  // refi terms, the operating percentages) are not on screen for a flip, so
  // they leave `createEmptyDealForm`'s defaults untouched and travel along —
  // the golden below is what freezes those.
  const expected: Record<string, unknown> = {
    deal_type: FLIP_PAYLOAD.deal_type,
    address: FLIP_PAYLOAD.address,
    section: FLIP_PAYLOAD.section,
    stage: FLIP_PAYLOAD.stage,
  };
  for (const field of FLIP_FORM_FIELDS) {
    expected[field] = (FLIP_PAYLOAD as Record<string, unknown>)[field];
  }
  expect(saved[0]!.body).toMatchObject(expected);
  // The mirror: never typed, always sent.
  expect((saved[0]!.body as Record<string, unknown>).arv_in_thousands).toBe(
    FLIP_PAYLOAD.salePrice,
  );

  await api.expectContract('analyze-flip-save', { rendered });
});
