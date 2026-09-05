import {
  BRRRR_FORM_FIELDS,
  BRRRR_PAYLOAD,
  expect,
  fillForm,
  test,
} from '../fixtures';

/**
 * The whole "new BRRRR deal" journey, end to end: type the numbers, name the
 * property, save, land on My Deals with the deal's modal already open on its
 * analysis. This is the app's primary path, so its network contract is the
 * most valuable thing in the suite.
 */

const RESULT_KEYS = [
  'cash_flow',
  'cash_out',
  'cash_out_routi',
  'cash_on_cash',
  'dscr',
  'equity',
  'roi',
  'net_profit',
  'total_cash_needed_for_deal',
  'total_cash_needed_for_deal_with_buffer',
];

test('analyze a BRRRR deal, save it, and land on its open modal', async ({
  page,
  api,
  settle,
}) => {
  const navigations: string[] = [];
  page.on('framenavigated', (frame) => {
    if (frame === page.mainFrame()) navigations.push(frame.url());
  });

  await page.goto('/analyze');
  await expect(page.getByTestId('form.root')).toBeVisible();

  await fillForm(page, BRRRR_FORM_FIELDS, BRRRR_PAYLOAD);

  await page.getByTestId('analyze.analyze-save').click();
  await expect(page.getByTestId('analyze.modal')).toBeVisible();

  await page.getByTestId('analyze.modal.address').fill(BRRRR_PAYLOAD.address);
  await page
    .getByTestId('analyze.modal.section')
    .selectOption(String(BRRRR_PAYLOAD.section));
  await page
    .getByTestId('analyze.modal.stage')
    .selectOption(String(BRRRR_PAYLOAD.stage));

  await page.getByTestId('analyze.modal.save').click();

  // The save pushes `/my-deals?openDeal=…`; `MyDeals` opens the modal and then
  // `router.replace`s the query away.
  await expect(page.getByTestId('mydeals.modal')).toBeVisible();
  expect(
    navigations.some((url) => url.includes('openDeal=')),
    'navigated through /my-deals?openDeal=<id>',
  ).toBe(true);
  await expect.poll(() => new URL(page.url()).search).toBe('');
  await expect.poll(() => new URL(page.url()).pathname).toBe('/my-deals');

  // The modal re-analyzes on a 500 ms debounce.
  await settle(600);
  await expect(page.getByTestId('mydeals.modal.results')).toBeVisible();

  const rendered: Record<string, string> = {};
  for (const key of RESULT_KEYS) {
    rendered[key] = (
      await page.getByTestId(`mydeals.modal.result.${key}`).innerText()
    ).trim();
  }

  // The saved body must be the fixture, field for field.
  const saved = api.matching(
    (request) => request.method === 'POST' && request.path === '/active-deals',
  );
  expect(saved).toHaveLength(1);
  expect(saved[0]!.body).toMatchObject({ ...BRRRR_PAYLOAD });

  await api.expectContract('analyze-brrr-save', { rendered });
});
