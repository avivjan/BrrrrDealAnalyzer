import { expect, test } from '../fixtures';
import { fieldInput, openTabOf } from '../fixtures/form';

/**
 * "Estimate ARV with Claude": the button in the deal form opens a popup that
 * posts to `/arv-estimate`, renders Claude's template and, on Apply, writes the
 * numbers into the form.
 *
 * An estimate is a background job: `POST /arv-estimate` answers 202 with a job
 * id at once, and the popup polls `GET /arv-estimate/{id}` every 3 s (a real
 * estimate outlasts Netlify's ~30 s proxy limit). The throwaway backend has no
 * ANTHROPIC_API_KEY (verify_regression scrubs it), so the real POST comes back
 * 503 "not configured" and the popup shows it. The job itself is mocked —
 * RUNNING on the first poll, SUCCEEDED on the next — because Claude and live
 * web search are not part of an e2e run; what is asserted is the UI: the
 * request it sends, that it keeps polling, the comps it shows, and where Apply
 * writes. The page clock is frozen, so `settle` drives the poll interval.
 */

const ARV_ESTIMATE_JOB_ID = 'e2e0123456789abcdef0123456789ab';

/** Mock the job: the POST starts it, the first poll says RUNNING, every later poll SUCCEEDED. */
async function mockArvEstimateJob(page: import('@playwright/test').Page, sentStartBodies: unknown[] = []) {
  let pollCount = 0;
  await page.route('**/arv-estimate', async (route) => {
    sentStartBodies.push(route.request().postDataJSON());
    await route.fulfill({
      status: 202,
      contentType: 'application/json',
      body: JSON.stringify({ arv_estimate_job_id: ARV_ESTIMATE_JOB_ID, status: 'RUNNING', arv_estimate: null, failure_message: null }),
    });
  });
  await page.route(`**/arv-estimate/${ARV_ESTIMATE_JOB_ID}`, async (route) => {
    pollCount += 1;
    const isFinished = pollCount > 1;
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        arv_estimate_job_id: ARV_ESTIMATE_JOB_ID,
        status: isFinished ? 'SUCCEEDED' : 'RUNNING',
        arv_estimate: isFinished ? CLAUDE_ARV_ESTIMATE : null,
        failure_message: null,
      }),
    });
  });
  return { pollCount: () => pollCount };
}

/**
 * Step the frozen clock a second at a time until the popup has polled `expectedPollCount` times.
 * Each poll timer is only set once the previous response has been handled, so one big jump can miss it.
 */
async function settleUntilPolled(
  settle: (milliseconds: number) => Promise<void>,
  pollCount: () => number,
  expectedPollCount: number,
): Promise<void> {
  await expect
    .poll(async () => {
      if (pollCount() < expectedPollCount) await settle(1000);
      return pollCount();
    }, { timeout: 30_000 })
    .toBeGreaterThanOrEqual(expectedPollCount);
}

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

test('a BRRRR estimate from the deal modal polls the job, then fills ARV and Lowest ARV', async ({ page, seed, settle }) => {
  const deal = await seed.seedActiveDeal('BRRRR', { section: 1 });
  const sentBodies: unknown[] = [];
  const arvEstimateJob = await mockArvEstimateJob(page, sentBodies);

  await page.goto('/my-deals');
  await page.getByTestId(`mydeals.card.${deal.id}`).click();
  await expect(page.getByTestId('mydeals.modal')).toBeVisible();
  await openTabOf(page, 'arv_in_thousands');

  await page.getByTestId('form.action.estimateArvWithClaude').click();
  await expect(page.getByTestId('arvEstimate.costNote')).toContainText('$0.10–0.50');
  await page.getByTestId('arvEstimate.note').fill('Full gut rehab, adding a second bathroom.');
  await page.getByTestId('arvEstimate.submit').click();

  await expect(page.getByTestId('arvEstimate.loading')).toBeVisible();
  await settleUntilPolled(settle, arvEstimateJob.pollCount, 1);
  await expect(page.getByTestId('arvEstimate.loading')).toBeVisible();
  await settleUntilPolled(settle, arvEstimateJob.pollCount, 2);

  await expect(page.getByTestId('arvEstimate.result.targetArv')).toContainText('$205,000');
  expect(arvEstimateJob.pollCount()).toBe(2);
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

test('a FLIP estimate on the Analyze page fills the projected sale price', async ({ page, settle }) => {
  const arvEstimateJob = await mockArvEstimateJob(page);

  await page.goto('/analyze');
  await page.getByTestId('analyze.type-flip').click();
  await openTabOf(page, 'salePrice');

  await page.getByTestId('form.action.estimateArvWithClaude').click();
  await expect(page.getByTestId('arvEstimate.strategy')).toContainText('Flip');
  await page.getByTestId('arvEstimate.address').fill('77 Flip Lane, Akron, OH');
  await page.getByTestId('arvEstimate.submit').click();
  await settleUntilPolled(settle, arvEstimateJob.pollCount, 2);
  await expect(page.getByTestId('arvEstimate.result.daysOnMarket')).toContainText('22 days');

  await page.getByTestId('arvEstimate.apply').click();
  await expect(fieldInput(page, 'salePrice')).toHaveValue(/205,000/);
});
