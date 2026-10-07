import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import AxeBuilder from '@axe-core/playwright';
import type { BrowserContext, Page } from '@playwright/test';
import { test, expect } from '../fixtures';

/**
 * The Member Loan end to end, with two real members on chromium's virtual
 * authenticator (tasks/todo/MemberLoan.md, Tests > E2E):
 *
 *   Aviv proposes a withdrawal: nothing changes. Yarden sees it waiting, approves
 *   it, and Amount Owed moves. Yarden proposes the reversal, Aviv approves it,
 *   and the loan is back where it started. A change the agreement has no
 *   clause for needs its written agreement. Statements and the CSV download.
 *   Someone who is not a member gets the refusal and no link.
 *
 * The backend's members are `e2e-aviv` and `e2e-yarden` (e2e/backend/serve_throwaway.py).
 * The device clock is moved to Oct 6, 2026, a date after the loan started and
 * not after the server's own "today", so the device's date is a valid change date.
 */

const BACKEND = fileURLToPath(new URL('../../../BackEnd', import.meta.url));
const TEST_DB = process.env.TEST_DATABASE_URL || 'postgresql+psycopg2://brrrr_test:brrrr_test@127.0.0.1:55432/brrrr_test';
const DEVICE_TODAY = new Date('2026-10-06T12:00:00');

function enrollmentLink(username: string, displayName: string): string {
  const out = execFileSync('python3', ['-m', 'manage', 'enroll', username, '--display-name', displayName], {
    cwd: BACKEND,
    env: { ...process.env, DATABASE_URL: TEST_DB, PYTHONDONTWRITEBYTECODE: '1', APP_ENV: 'development', AUTH_APP_ORIGIN: 'http://localhost:5173' },
    encoding: 'utf8',
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  return out.trim().split('\n').pop()!.replace('http://localhost:5173', '');
}

async function signedInMember(context: BrowserContext, page: Page, username: string, displayName: string): Promise<Page> {
  const cdp = await context.newCDPSession(page);
  await cdp.send('WebAuthn.enable');
  await cdp.send('WebAuthn.addVirtualAuthenticator', {
    options: { protocol: 'ctap2', transport: 'internal', hasResidentKey: true, hasUserVerification: true, isUserVerified: true, automaticPresenceSimulation: true },
  });
  await page.goto(enrollmentLink(username, displayName));
  await page.getByTestId('enroll.label').fill('Playwright');
  await page.getByTestId('enroll.create').click();
  await expect(page).toHaveURL(/\/$/);
  await page.clock.setFixedTime(DEVICE_TODAY);
  return page;
}

async function amountOwed(page: Page): Promise<string> {
  await page.goto('/member-loan?tab=today');
  const tile = page.getByTestId('member-loan.amount-owed');
  await expect(tile).toContainText('$');
  return (await tile.textContent())!.match(/\$[\d,]+\.\d{2}/)![0];
}

test.describe('member loan', () => {
  test.skip(({ browserName }) => browserName !== 'chromium', 'virtual authenticator needs CDP');

  test('two-party approval, reversal, statements, and the gate', async ({ browser, page, context }) => {
    const aviv = await signedInMember(context, page, 'e2e-aviv', 'Aviv');
    const yardenContext = await browser.newContext();
    const yarden = await signedInMember(yardenContext, await yardenContext.newPage(), 'e2e-yarden', 'Yarden');

    // The session strip links the loan for a member.
    await aviv.goto('/');
    await expect(aviv.getByTestId('security.member-loan-link')).toBeVisible();

    const before = await amountOwed(aviv);

    // Aviv proposes a withdrawal of $100.00 dated today on his device.
    await aviv.getByTestId('member-loan.tab-propose').click();
    await aviv.getByTestId('member-loan.amount-input').fill('100');
    await expect(aviv.getByTestId('member-loan.amount-helper')).toHaveText('Exactly $100.00');
    await aviv.getByTestId('member-loan.check').click();
    await expect(aviv.getByTestId('member-loan.preview')).toBeVisible();
    await aviv.getByTestId('member-loan.send').click();
    await expect(aviv.getByTestId('member-loan.notice')).toContainText('Nothing changes until they approve it');
    expect(await amountOwed(aviv)).toBe(before);

    // Yarden approves it.
    await yarden.goto('/member-loan?tab=waiting');
    // Newest first: a leftover from an earlier local run (the server is reused) never wins.
    const waiting = yarden.getByTestId('member-loan.proposal').filter({ hasText: 'Withdrawal by Aviv of $100.00' }).first();
    await expect(waiting).toBeVisible();
    await waiting.getByTestId('member-loan.approve').click();
    await expect(yarden.getByTestId('member-loan.notice')).toContainText('Approved');
    const after = await amountOwed(aviv);
    expect(after).not.toBe(before);

    // The history shows who proposed and who approved it.
    await aviv.getByTestId('member-loan.tab-history').click();
    await expect(aviv.getByTestId('member-loan.ledger-row').filter({ hasText: 'Proposed by Aviv, approved by Yarden' }).first()).toBeVisible();

    // Yarden proposes the reversal; Aviv approves it; the loan is back where it was.
    await yarden.goto('/member-loan?tab=history');
    const approvedCard = yarden.getByTestId('member-loan.proposal').filter({ hasText: 'Withdrawal by Aviv of $100.00' }).first();
    await approvedCard.getByTestId('member-loan.reverse-open').click();
    await approvedCard.getByTestId('member-loan.reverse-reason').fill('E2E clean-up');
    await approvedCard.getByTestId('member-loan.reverse').click();
    await expect(yarden.getByTestId('member-loan.notice')).toContainText('reversal was sent');
    await aviv.goto('/member-loan?tab=waiting');
    await aviv.getByTestId('member-loan.proposal').filter({ hasText: 'It reverses' }).first().getByTestId('member-loan.approve').click();
    await expect(aviv.getByTestId('member-loan.notice')).toContainText('Approved');
    expect(await amountOwed(aviv)).toBe(before);

    // A Yarden withdrawal needs the written agreement before it can be checked.
    await yarden.goto('/member-loan?tab=propose');
    await yarden.getByTestId('member-loan.type-yarden_additional_withdrawal_increase').check();
    await yarden.getByTestId('member-loan.amount-input').fill('20');
    await expect(yarden.getByTestId('member-loan.check')).toBeDisabled();
    await yarden.locator('#member-loan-agreement-date').fill('2026-10-05');
    await yarden.locator('#member-loan-agreement-description').fill('Side letter');
    await expect(yarden.getByTestId('member-loan.check')).toBeEnabled();

    // Statements and the CSV.
    await aviv.goto('/member-loan?tab=statements&month=2026-10');
    await expect(aviv.getByTestId('member-loan.statement')).toContainText('1. Summary');
    await expect(aviv.getByTestId('member-loan.statement')).toContainText('This statement is binding unless either party objects in writing within 30 days');
    const pdf = aviv.waitForEvent('download');
    await aviv.getByTestId('member-loan.pdf').click();
    expect((await pdf).suggestedFilename()).toBe('member-loan-statement-2026-10.pdf');
    await aviv.goto('/member-loan?tab=history');
    const csv = aviv.waitForEvent('download');
    await aviv.getByTestId('member-loan.csv').click();
    expect((await csv).suggestedFilename()).toMatch(/^member-loan-ledger-through-2026-10-06\.csv$/);

    // No serious accessibility problem on the page. axe runs on timers, which the
    // fixed device clock would never fire (the same reason e2e/fixtures/axe.ts resumes it).
    await aviv.clock.resume();
    const axe = await new AxeBuilder({ page: aviv }).include('[data-testid="member-loan.page"]').analyze();
    expect(axe.violations.filter((v) => v.impact === 'serious' || v.impact === 'critical').map((v) => v.id)).toEqual([]);

    // Someone signed in who is not a member: the refusal, and no link.
    const outsiderContext = await browser.newContext();
    const outsider = await signedInMember(outsiderContext, await outsiderContext.newPage(), `e2e-outsider-${Date.now()}`, 'Outsider');
    await outsider.goto('/');
    await expect(outsider.getByTestId('security.bar')).toBeVisible();
    await expect(outsider.getByTestId('security.member-loan-link')).toHaveCount(0);
    await outsider.goto('/member-loan');
    await expect(outsider.getByTestId('member-loan.refused')).toContainText('only for the two members');

    await yardenContext.close();
    await outsiderContext.close();
  });
});
