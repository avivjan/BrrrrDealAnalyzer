import { expect, test, typeInto } from '../fixtures';

/**
 * The "send a market offer" modal on the landing page.
 *
 * Two real cases and one mocked one. The real ones are what this environment
 * can actually produce: an incomplete form that never reaches the network, and
 * a complete one that does and comes back refused, because SMTP credentials
 * are scrubbed on the throwaway backend. The success path is mocked, because
 * the only thing worth asserting about it is the *UI* — that it closes itself
 * and forgets what you typed.
 */

const OFFER = {
  agentName: 'Dana Broker',
  agentEmail: 'dana@example.com',
  address: '9 Offer Way',
  purchasePrice: 250_000,
  inspectionDays: 7,
};

async function fillOffer(page: import('@playwright/test').Page): Promise<void> {
  await page.getByTestId('offer.agent-name').fill(OFFER.agentName);
  await page.getByTestId('offer.agent-email').fill(OFFER.agentEmail);
  await page.getByTestId('offer.property-address').fill(OFFER.address);
  // A `MoneyInput` outside the deal form; same commit-on-blur rules apply.
  await typeInto(
    page.getByTestId('offer.purchase-price').locator('input'),
    String(OFFER.purchasePrice),
  );
  await page.getByTestId('offer.inspection-days').fill(String(OFFER.inspectionDays));
}

test('an empty offer is refused locally', async ({ page, api }) => {
  await page.goto('/');
  await page.getByTestId('landing.offer').click();
  await expect(page.getByTestId('offer.root')).toBeVisible();

  api.reset();

  await page.getByTestId('offer.send').click();
  await expect(page.getByTestId('offer.message')).toHaveText(
    'Please fill in all required fields.',
  );
  await expect(page.getByTestId('offer.root')).toBeVisible();

  await api.expectNoRequests('an incomplete offer must not reach the server');
});

test('a complete offer posts and surfaces the server refusal', async ({
  page,
  api,
}) => {
  await page.goto('/');
  await page.getByTestId('landing.offer').click();
  await expect(page.getByTestId('offer.root')).toBeVisible();

  await fillOffer(page);

  api.reset();

  await page.getByTestId('offer.send').click();

  // Credentials are scrubbed on the throwaway backend, so `/send-offer`
  // answers 500 with `Failed to send email: Email password not configured`
  // and the modal renders that detail verbatim.
  await expect(page.getByTestId('offer.message')).toHaveText(
    'Failed to send email: Email password not configured',
  );
  await expect(page.getByTestId('offer.root')).toBeVisible();

  await api.expectContract('send-offer');
});

test('a successful offer closes and resets the modal', async ({
  page,
  settle,
}) => {
  await page.route('**/send-offer', async (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, message: 'ok' }),
    }),
  );

  await page.goto('/');
  await page.getByTestId('landing.offer').click();
  await fillOffer(page);
  await page.getByTestId('offer.send').click();

  await expect(page.getByTestId('offer.message')).toHaveText(
    'Offer sent successfully!',
  );

  // The modal closes itself 1.5 s later and clears every field.
  await settle(1500);
  await expect(page.getByTestId('offer.root')).toHaveCount(0);

  await page.getByTestId('landing.offer').click();
  await expect(page.getByTestId('offer.agent-name')).toHaveValue('');
  await expect(page.getByTestId('offer.property-address')).toHaveValue('');
});
