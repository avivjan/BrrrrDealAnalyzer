import { expect, test } from '../fixtures';
import { API_ORIGIN } from '../fixtures/env';

/**
 * The property inspection walkthrough (tasks/todo/PropertyInspection.md):
 * public by link, one card per item, follow-ups only when relevant, the
 * window counter, the finish gate with its typed override, and the summary.
 * Each answer is saved as a PATCH of one item after a 600 ms pause.
 */

async function startInspection(page: import('@playwright/test').Page, settle: (ms: number) => Promise<void>) {
  await page.goto('/inspections');
  await page.getByTestId('inspections.new').click();
  await page.getByTestId('inspection.start.address').fill('12 Palm Ave, Tampa, FL');
  await page.getByTestId('inspection.start.next').click();
  await page.getByTestId('inspection.start.next').click();
  await page.getByTestId('inspection.start.inspector').fill('Aviv');
  await page.getByTestId('inspection.start.begin').click();
  await expect(page.getByTestId('inspection.map.item.roof')).toBeVisible();
  await settle(100);
}

test('walk an inspection: cards, follow-ups, counter, finish gate, summary', async ({ page, api, settle }) => {
  await startInspection(page, settle);
  await expect(page.getByTestId('inspection.missions')).toContainText('8');

  // Roof from the map: status, then its fields one at a time.
  await page.getByTestId('inspection.map.item.roof').click();
  await page.getByTestId('inspection.card.status.repair').click();
  await page.getByTestId('inspection.field.roof_type.shingle').click();
  await page.getByTestId('inspection.field.roof_install_year.unknown').click();
  await expect(page.getByTestId('inspection.card.notes')).toBeVisible();
  await settle(700);
  await expect(page.getByTestId('inspection.missions')).toContainText('7');

  // Next card with the ◀ ▶ bar, then the window counter.
  await page.getByTestId('inspection.card.next').click();
  await page.getByTestId('inspection.card.next').click();
  await page.getByTestId('inspection.card.next').click();
  await expect(page.getByRole('heading', { name: 'Windows' })).toBeVisible();
  await page.getByTestId('inspection.card.status.replace').click();
  for (let step = 0; step < 3; step += 1) await page.getByTestId('inspection.counter.increase').click();
  await page.getByTestId('inspection.counter.decrease').click();
  await expect(page.getByTestId('inspection.counter.value')).toHaveText('2');
  await settle(700);

  // Sewer: the pump date only appears for a septic tank.
  await page.getByTestId('inspection.card.map').click();
  await page.getByTestId('inspection.map.item.sewer').click();
  await page.getByTestId('inspection.card.status.ok').click();
  await page.getByTestId('inspection.field.sewer_type.septic').click();
  await expect(page.getByTestId('inspection.field.septic_last_pump_date.date')).toBeVisible();
  await page.getByTestId('inspection.card.answer.sewer_type').click();
  await page.getByTestId('inspection.field.sewer_type.city').click();
  await expect(page.getByTestId('inspection.field.septic_last_pump_date.date')).toHaveCount(0);
  await settle(700);

  // Finishing is blocked while missions are left; the override needs a reason.
  await page.getByTestId('inspection.card.map').click();
  await expect(page.getByTestId('inspection.finish.blocked')).toContainText('6 missions left');
  await page.getByTestId('inspection.finish').click();
  await expect(page.getByTestId('inspection.finish-dialog.confirm')).toBeDisabled();
  await page.getByTestId('inspection.finish-dialog.reason').fill('Utilities were shut off today');
  await page.getByTestId('inspection.finish-dialog.confirm').click();
  await expect(page.getByTestId('inspection.finished')).toBeVisible();
  await page.getByTestId('inspection.finished.summary').click();

  await expect(page.getByTestId('inspection.summary.replace')).toContainText('Windows');
  await expect(page.getByTestId('inspection.summary.repair')).toContainText('Roof');
  await expect(page.getByTestId('inspection.summary.windows')).toContainText('2');
  await expect(page.getByTestId('inspection.summary.override')).toContainText('Utilities were shut off today');

  const itemPatches = api.matching((request) => request.method === 'PATCH' && request.path.startsWith('/public/inspections/{id}/items/'));
  expect(itemPatches.map((request) => request.path)).toEqual([
    '/public/inspections/{id}/items/roof',
    '/public/inspections/{id}/items/windows',
    '/public/inspections/{id}/items/sewer',
  ]);
  expect(itemPatches[2]!.body).toEqual({ item_status: 'ok', item_field_values: { sewer_type: 'city' } });

  await api.expectContract('inspection-walkthrough');
});

test('a swipe moves to the next card', async ({ page, settle }) => {
  await startInspection(page, settle);
  await page.getByTestId('inspection.map.item.roof').click();
  const cardArea = page.getByTestId('inspection.card-area');
  const box = (await cardArea.boundingBox())!;
  const y = box.y + 40;
  await page.mouse.move(box.x + box.width * 0.8, y);
  await page.mouse.down();
  await page.mouse.move(box.x + box.width * 0.2, y + 5, { steps: 5 });
  await page.mouse.up();
  await expect(page.getByRole('heading', { name: 'Foundation' })).toBeVisible();
});

test('an anonymous visitor opens an inspection link without being sent to login', async ({ page, settle }) => {
  await startInspection(page, settle);
  const inspectionUrl = new URL(page.url()).pathname;

  // The API now enforces sessions and this browser has none.
  await page.route(`${API_ORIGIN}/auth/config`, (route) =>
    route.fulfill({ json: { auth_mode: 'enforce', device_policy: 'off', rp_id: 'localhost' } }),
  );
  await page.route(`${API_ORIGIN}/auth/me`, (route) => route.fulfill({ status: 401, json: { detail: 'unauthenticated' } }));
  await page.route(`${API_ORIGIN}/auth/refresh`, (route) => route.fulfill({ status: 401, json: { detail: 'unauthenticated' } }));
  await page.goto(inspectionUrl);

  await expect(page.getByTestId('inspection.header.address')).toHaveText('12 Palm Ave, Tampa, FL');
  await expect(page).toHaveURL(new RegExp(`${inspectionUrl}$`));

  // Linking needs a login, and comes back to this inspection afterwards.
  await page.getByTestId('inspection.link-deal').click();
  await expect.poll(() => new URL(page.url()).pathname).toBe('/login');
  expect(new URL(page.url()).searchParams.get('next')).toBe(inspectionUrl);
});
