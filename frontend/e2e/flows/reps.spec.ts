import { expect, test } from '../fixtures';

/**
 * The REPS hour tracker.
 *
 * Google Sheets and GCS credentials are scrubbed on the throwaway backend, so
 * this page runs in its "not connected" state — which is the honest thing to
 * characterize, because that is also what it does on a fresh clone and the
 * banner is the only thing telling the user why nothing saves. The people
 * directory and the stopwatch are database- and browser-local, so those work
 * fully and are asserted properly.
 */

const NOT_CONFIGURED_DETAIL =
  'REPS feature is not fully configured. Missing env vars: REPS_SHEET_ID_AVIV, ' +
  'REPS_SHEET_ID_YARDEN, REPS_GCS_BUCKET. See REPS_README.md for setup instructions.';

/** The stopwatch persists per user under its own localStorage key. */
const TIMER_KEY = 'timer_state_aviv';

const PNG_1X1 = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==',
  'base64',
);

test('the tracker loads unconfigured and says so', async ({ page, api }) => {
  await page.goto('/reps');

  await expect(page.getByTestId('reps.config-banner')).toBeVisible();
  await expect(page.getByTestId('reps.config-banner')).toContainText(
    NOT_CONFIGURED_DETAIL,
  );

  await api.expectContract('reps-load');
});

test('the people directory adds and removes contacts', async ({
  page,
  api,
  dialogs,
}) => {
  await page.goto('/reps');
  await page.getByTestId('reps.people-toggle').click();
  await expect(page.getByTestId('repspeople.empty')).toBeVisible();

  api.reset();

  await page.getByTestId('repspeople.new-name').fill('Gilly Plumber');
  await page.getByTestId('repspeople.new-role').fill('Plumber');
  await page.getByTestId('repspeople.add').click();

  const person = page.locator('[data-testid^="repspeople.person."]').first();
  await expect(person).toContainText('Gilly Plumber');

  await page
    .locator('[data-testid^="repspeople.person."][data-testid$=".delete"]')
    .first()
    .click();

  await dialogs.expectDialogs([
    'Delete this person? Existing log entries will keep the name.',
  ]);
  await expect(page.getByTestId('repspeople.empty')).toBeVisible();

  await api.expectContract('reps-people');
});

test('the stopwatch starts, stops and discards behind a confirm', async ({
  page,
  dialogs,
  settle,
}) => {
  await page.goto('/reps');
  await expect(page.getByTestId('repstimer.start')).toBeVisible();

  const stored = () => page.evaluate((key) => localStorage.getItem(key), TIMER_KEY);

  await page.getByTestId('repstimer.start').click();
  await expect(page.getByTestId('repstimer.stop')).toBeVisible();
  const running = JSON.parse((await stored())!);
  expect(running.running).toBe(true);
  expect(running.sessionStartedAt).not.toBeNull();

  // Ninety seconds of clocked-in time.
  await settle(90_000);
  await page.getByTestId('repstimer.stop').click();
  await expect(page.getByTestId('repstimer.resume')).toBeVisible();
  const paused = JSON.parse((await stored())!);
  expect(paused.running).toBe(false);
  expect(paused.accumulatedMs).toBe(90_000);

  await page.getByTestId('repstimer.discard').click();
  await dialogs.expectDialogs([
    'Discard this stopwatch session? Timer, GPS breadcrumbs, and queued evidence will reset.',
  ]);

  await expect(page.getByTestId('repstimer.start')).toBeVisible();
  const cleared = JSON.parse((await stored())!);
  expect(cleared.accumulatedMs).toBe(0);
  expect(cleared.sessionStartedAt).toBeNull();
});

test('a manual entry with evidence uploads and is refused by the backend', async ({
  page,
  api,
}) => {
  await page.goto('/reps');
  await page.getByTestId('reps.manual-entry').click();
  await expect(page.getByTestId('repsmodal.root')).toBeVisible();

  await page.getByTestId('repsmodal.file-input').setInputFiles({
    name: 'site-visit.png',
    mimeType: 'image/png',
    buffer: PNG_1X1,
  });
  await expect(page.getByTestId('repsmodal.local-file.0')).toBeVisible();

  await page
    .getByTestId('repsmodal.description')
    .fill('Walked the roof with the GC and priced the tear-off.');
  await page.getByTestId('repsmodal.start-time').fill('2026-09-04T08:00');
  await page.getByTestId('repsmodal.end-time').fill('2026-09-04T10:30');

  api.reset();

  await page.getByTestId('repsmodal.save').click();

  await expect(page.getByTestId('repsmodal.error')).toHaveText(
    NOT_CONFIGURED_DETAIL,
  );
  await expect(page.getByTestId('repsmodal.root')).toBeVisible();

  const upload = api.matching(
    (request) => request.path === '/reps/upload-batch',
  );
  expect(upload).toHaveLength(1);
  // `property_name` and `activity_category` are only appended when set, so an
  // entry with neither carries exactly the user and the client-side stamp.
  expect(upload[0]!.body).toEqual({ fields: ['log_timestamp', 'user'], files: 1 });

  await api.expectContract('reps-manual-entry');
});
