import { BRRRR_FORM_FIELDS, BRRRR_PAYLOAD, expect, fillForm, test } from '../fixtures';
import { fieldInput, fieldRoot, openTabOf, setField, typeInto } from '../fixtures/form';

/**
 * The closing-cost estimates explain themselves. Next to each input on its formula default
 * the form says how the figure is built (the Florida title estimate line by line, the
 * recording formula, the two refi ones); typing a dollar amount over it hides the
 * explanation. The breakdown popup tells the same story step by step.
 *
 * A $100k purchase at 0% down with a $23k construction budget is a $123k hard-money loan:
 * paying all closing costs, the title estimate is exactly $1,540 ($600 office fees + $575
 * owner's policy + $365 lender's policy).
 */
test('the Florida title estimate and the recording estimate are explained next to their inputs', async ({ page }) => {
  await page.goto('/analyze');
  await expect(page.getByTestId('form.root')).toBeVisible();
  await fillForm(page, BRRRR_FORM_FIELDS, { ...BRRRR_PAYLOAD, purchasePrice: 100, down_payment: 0 });
  await setField(page, 'constructionLoanBudget', 23);

  await openTabOf(page, 'titleEscrowBuy');
  await fieldRoot(page, 'titleModeBuy').locator('select').selectOption('we_pay_all');
  await expect(fieldInput(page, 'titleEscrowBuy')).toHaveValue('$1,540');
  const titleExplanation = fieldRoot(page, 'titleEscrowBuy').locator('[data-part="estimate-explanation"] li');
  await expect(titleExplanation).toHaveText([
    'Office fees $600: $350 settlement + $150 title search + $100 municipal lien search',
    "Owner's policy $575: FL promulgated rate (F.A.C. 69O-186.003), $100,000 ÷ $1,000 × $5.75",
    "Lender's policy $365: $250 endorsements (ALTA 8.1, Form 9, simultaneous issue) + $5.00 per $1,000 of the $23,000 loan above the price",
  ]);

  const recordingExplanation = fieldRoot(page, 'recordingTransferBuy').locator('[data-part="estimate-explanation"]');
  await expect(recordingExplanation).toContainText('$250 + 0.55% × $123,000 + $700 = $1,626.50');
  await typeInto(fieldInput(page, 'recordingTransferBuy'), '1500');
  await expect(recordingExplanation).toHaveCount(0);
  await fieldRoot(page, 'recordingTransferBuy').locator('[data-part="reset"]').click();
  await expect(recordingExplanation).toContainText('$250 + 0.55% × $123,000 + $700 = $1,626.50');

  await openTabOf(page, 'titleEscrowRefi');
  await expect(fieldRoot(page, 'recordingTransferRefi').locator('[data-part="estimate-explanation"]')).toContainText('0.55% × $240,000 refi loan + $250 = $1,570');
  await expect(fieldRoot(page, 'titleEscrowRefi').locator('[data-part="estimate-explanation"]')).toContainText('$800 + 0.45% × $240,000 refi loan = $1,880');
});

test('the breakdown popup opens Title & Escrow (Buy) into its three Florida lines', async ({ page, seed, settle }) => {
  const deal = await seed.seedBoughtDeal('BRRRR', { purchasePrice: 100, down_payment: 0, constructionLoanBudget: 23, titleModeBuy: 'we_pay_all' });
  await page.goto('/bought-deals');
  await page.getByTestId(`boughtdeals.card.${deal.id}`).click();
  await expect(page.getByTestId('boughtdeals.modal')).toBeVisible();
  await settle(400);
  await page.getByTestId('result-tile.cash_out.show-calculation').click();
  const popup = page.getByTestId('calculation-breakdown-popup');
  await expect(popup).toBeVisible();

  for (const stepLabel of ['Cash to Close (Buy)', 'Closing Costs (Buy)', 'Title & Escrow']) {
    await popup.getByRole('button', { name: `Show how ${stepLabel} is calculated` }).first().click();
  }
  // The three Florida lines are Title & Escrow's operands, and its note explains each of them.
  await expect(popup).toContainText("+Office & Search Fees$600+Owner's Title Policy$575+Lender's Title Policy & Endorsements$365=Title & Escrow (Buy)$1,540");
  await expect(popup).toContainText('$350 settlement / closing fee + $150 title search + $100 municipal lien search');
  await expect(popup).toContainText('Florida statutory promulgated rate (F.A.C. 69O-186.003): $5.75 per $1,000 of the purchase price up to $100,000');
  await expect(popup).toContainText('$250 covers the Florida ALTA 8.1 and Form 9 endorsements and the simultaneous-issue rate');
});
