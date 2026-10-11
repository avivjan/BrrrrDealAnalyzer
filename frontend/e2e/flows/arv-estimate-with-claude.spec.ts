import { expect, test } from '../fixtures';
import { fieldInput, openTabOf } from '../fixtures/form';

/**
 * "Estimate ARV with Claude": the button in the deal form opens a popup that
 * posts to `/arv-estimate`, renders Claude's template and, on Apply, writes the
 * numbers into the form.
 *
 * Two real cases and two mocked ones. The throwaway backend has no
 * ANTHROPIC_API_KEY (verify_regression scrubs it), so the real request comes
 * back 503 "not configured" and the popup shows it. The answer itself is
 * mocked: Claude and live web search are not part of an e2e run, and what is
 * worth asserting is the UI — the request it sends, the comps it shows, and
 * where Apply writes.
 */

const CLAUDE_ARV_ESTIMATE = {
  estimated_arv_range_low: 195000,
  estimated_arv_range_high: 215000,
  target_arv: 205000,
  conservative_lowest_arv: 190000,
  confidence_score_1_to_10: 7,
  average_days_on_market_of_sold_comparables: 22,
  median_days_on_market_of_sold_comparables: 18,
  market_pace_verdict: 'NORMAL',
  market_logic: 'Three renovated 3/2 sales within 0.3 mi carry the value.',
  subject_property_as_found: {
    bedrooms: 3, bathrooms: 1, square_feet: 1400, year_built: 1925, lot_size_square_feet: null, property_style: null,
  },
  sold_comparables: [
    {
      address: '130 Comp St',
      distance_from_subject_in_miles: 0.2,
      listing_status: 'SOLD',
      sale_or_list_date: '2026-08-01',
      sale_or_list_price: 205000,
      bedrooms: 3,
      bathrooms: 2,
      square_feet: 1380,
      year_built: 1925,
      lot_size_square_feet: null,
      price_per_square_foot: 148.55,
      days_on_market: 18,
      renovation_condition: 'Flip-grade renovated',
      adjusted_value_for_subject: 207000,
      adjustment_explanation: '+$2k for GLA',
      weight_in_valuation: 'PRIMARY',
      source_url: 'https://www.redfin.com/130-Comp-St',
    },
  ],
  active_or_pending_comparables: [],
  discarded_comparables: [],
  data_caveats: [],
  source_urls: [],
};

test('without a server key the popup shows "not configured"', async ({ page, seed }) => {
  const deal = await seed.seedActiveDeal('BRRRR', { section: 1 });
  await page.goto('/my-deals');
  await page.getByTestId(`mydeals.card.${deal.id}`).click();
  await expect(page.getByTestId('mydeals.modal')).toBeVisible();

  await page.getByTestId('form.tab.refinance').click();
  await page.getByTestId('form.action.estimateArvWithClaude').click();
  await expect(page.getByTestId('arvEstimate.root')).toBeVisible();
  await expect(page.getByTestId('arvEstimate.address')).toHaveValue(deal.address);

  await page.getByTestId('arvEstimate.submit').click();
  await expect(page.getByTestId('arvEstimate.error')).toHaveText('ARV estimate is not configured on the server.');
});

test('a BRRRR estimate from the deal modal fills ARV and Lowest ARV', async ({ page, seed }) => {
  const deal = await seed.seedActiveDeal('BRRRR', { section: 1 });
  const sentBodies: unknown[] = [];
  await page.route('**/arv-estimate', async (route) => {
    sentBodies.push(route.request().postDataJSON());
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(CLAUDE_ARV_ESTIMATE) });
  });

  await page.goto('/my-deals');
  await page.getByTestId(`mydeals.card.${deal.id}`).click();
  await expect(page.getByTestId('mydeals.modal')).toBeVisible();
  await openTabOf(page, 'arv_in_thousands');

  await page.getByTestId('form.action.estimateArvWithClaude').click();
  await expect(page.getByTestId('arvEstimate.costNote')).toContainText('$0.10–0.50');
  await page.getByTestId('arvEstimate.note').fill('Full gut rehab, adding a second bathroom.');
  await page.getByTestId('arvEstimate.submit').click();

  await expect(page.getByTestId('arvEstimate.result.targetArv')).toContainText('$205,000');
  await expect(page.getByTestId('arvEstimate.result.soldComparables')).toContainText('130 Comp St');
  expect(sentBodies).toHaveLength(1);
  expect(sentBodies[0]).toMatchObject({
    deal_type: 'BRRRR',
    property_address: deal.address,
    investor_situation_note: 'Full gut rehab, adding a second bathroom.',
  });

  await page.getByTestId('arvEstimate.apply').click();
  await expect(page.getByTestId('arvEstimate.root')).toHaveCount(0);
  await expect(fieldInput(page, 'arv_in_thousands')).toHaveValue(/205,000/);
  await expect(fieldInput(page, 'lowestArv')).toHaveValue(/190,000/);
});

test('a FLIP estimate on the Analyze page fills the projected sale price', async ({ page }) => {
  await page.route('**/arv-estimate', (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(CLAUDE_ARV_ESTIMATE) }),
  );

  await page.goto('/analyze');
  await page.getByTestId('analyze.type-flip').click();
  await openTabOf(page, 'salePrice');

  await page.getByTestId('form.action.estimateArvWithClaude').click();
  await expect(page.getByTestId('arvEstimate.strategy')).toContainText('Flip');
  await page.getByTestId('arvEstimate.address').fill('77 Flip Lane, Akron, OH');
  await page.getByTestId('arvEstimate.submit').click();
  await expect(page.getByTestId('arvEstimate.result.daysOnMarket')).toContainText('22 days');

  await page.getByTestId('arvEstimate.apply').click();
  await expect(fieldInput(page, 'salePrice')).toHaveValue(/205,000/);
});
