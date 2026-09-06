import { BRRRR_PAYLOAD, expect, test } from '../fixtures';

/**
 * The branded deal report.
 *
 * The PDF is fetched as a blob, previewed inside the app, and only downloaded
 * if the user asks — so three things matter and all three are frozen here: the
 * request that produces it, that the response really is a PDF, and the file
 * name the browser is offered.
 */

const EXPECTED_FILENAME = `BigWhales_BRRRR_${BRRRR_PAYLOAD.address.replace(
  /[^A-Za-z0-9]+/g,
  '_',
)}.pdf`;

test('viewing a report fetches a PDF blob and previews it', async ({
  page,
  api,
  seed,
}) => {
  const deal = await seed.seedActiveDeal('BRRRR', { section: 1 });

  await page.goto('/my-deals');
  await page.getByTestId(`mydeals.card.${deal.id}`).click();
  await expect(page.getByTestId('mydeals.modal')).toBeVisible();

  api.reset();

  await page.getByTestId('mydeals.modal.view-report').click();

  const preview = page.getByTestId('mydeals.pdf-modal');
  await expect(preview).toBeVisible();
  await expect(page.getByTestId('mydeals.pdf-modal.iframe')).toHaveAttribute(
    'src',
    /^blob:/,
  );

  await api.expectContract('pdf-report');
});

test('the download button offers the branded filename', async ({ page, seed }) => {
  const deal = await seed.seedActiveDeal('BRRRR', { section: 1 });

  await page.goto('/my-deals');
  await page.getByTestId(`mydeals.card.${deal.id}`).click();
  await page.getByTestId('mydeals.modal.view-report').click();
  await expect(page.getByTestId('mydeals.pdf-modal')).toBeVisible();

  const [download] = await Promise.all([
    page.waitForEvent('download'),
    page.getByTestId('mydeals.pdf-modal.download').click(),
  ]);

  expect(download.suggestedFilename()).toBe(EXPECTED_FILENAME);
});
