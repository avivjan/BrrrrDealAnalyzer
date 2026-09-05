import type { Page } from '@playwright/test';

import { BRRRR_PAYLOAD, expect, fillForm, test } from '../fixtures';

/**
 * Nothing is still animating once the app has settled — checked with motion
 * *on*, across every route and every surface Phase 4 animates.
 *
 * `e2e/fixtures/motion.ts` has carried `expectNoLiveTweens` since Phase 0, but
 * it only ever ran on one modal (`deep-link-open`). This walks the whole app:
 * six routes, four modals opened and closed again. What it is looking for is
 * the failure mode a motion layer actually has — not a dropped frame, but a
 * tween that never reaches `onComplete` and so sits on `gsap.globalTimeline`
 * forever. That costs a `requestAnimationFrame` loop for the rest of the
 * session, keeps the element it targets pinned in memory, and (for a `leave`)
 * holds a `pointer-events: none` node over the page. None of it is visible in a
 * screenshot, and none of the four functional projects can see it either,
 * because they run with `reducedMotion: 'reduce'` and GSAP is inert there.
 *
 * ## Why the clock is faked rather than slept through
 *
 * The fixtures install a paused clock before the first navigation, and this
 * spec keeps it. That is not a compromise, it is what makes the check exact: a
 * tween created while the clock is paused cannot advance on its own, so
 * `settle(1000)` is the *only* time the page ever gets, and "quiet after one
 * simulated second" means precisely that rather than "quiet after a second of
 * wall clock, on this machine, today". GSAP drives itself from
 * `requestAnimationFrame`, which Playwright's clock fakes, so `clock.runFor`
 * plays a 250 ms tween exactly as a real second would — the `deep-link-open`
 * spec has relied on that since Task 4.3.
 *
 * The one thing the fake clock does not own is the network. Every step
 * therefore waits for its own end state (the modal visible, the results panel
 * rendered) *before* the settle that precedes the assertion, so a response can
 * never land mid-settle and start a reveal the assertion would then catch
 * half-run.
 *
 * ## Why it is not vacuous
 *
 * `expectNoLiveTweens` reads `window.gsap` and passes when it is undefined —
 * correct for the reduced-motion projects, useless as a guard if the bundle
 * ever stopped exposing the instance. So this spec reads the count itself: a
 * missing `window.gsap` is `-1` and fails immediately, and the walk has to
 * observe at least one live tween overall or it fails as staged theatre.
 */

/** A step's two readings: what was running, and what was left afterwards. */
interface Reading {
  step: string;
  /**
   * Children on the global timeline the instant the interaction returned.
   *
   * Zero is a legitimate reading: a step that had to run the clock forward to
   * reach its own end state (the two deal modals wait out a 500 ms re-analyze
   * debounce) has already played its tweens by the time this is read, and the
   * settings modal animates in CSS rather than in GSAP. So it is the *total*
   * across the walk, not each row, that the last assertion holds to.
   */
  running: number;
  /** Children left one simulated second later. Must be 0. */
  quiet: number;
}

/** Children on `gsap.globalTimeline`, or `-1` when the page exposes no GSAP. */
async function liveTweens(page: Page): Promise<number> {
  return page.evaluate(() =>
    window.gsap ? window.gsap.globalTimeline.getChildren().length : -1,
  );
}

test.beforeEach(({}, testInfo) => {
  test.skip(
    testInfo.project.name !== 'chromium-motion',
    'the motion-on guard; the other projects run with reducedMotion: reduce',
  );
});

test('no GSAP tween outlives its interaction, on any route @motion', async ({
  page,
  seed,
  settle,
}) => {
  const readings: Reading[] = [];

  /**
   * Record what this step started, give the page one simulated second, and
   * require the global timeline to be empty again.
   */
  const quietAfter = async (step: string): Promise<void> => {
    const running = await liveTweens(page);
    expect(running, `${step}: the page exposes window.gsap`).toBeGreaterThanOrEqual(0);
    await settle(1000);
    const quiet = await liveTweens(page);
    readings.push({ step, running, quiet });
    expect(quiet, `${step}: tweens still on the global timeline after 1 s`).toBe(0);
  };

  // Seeded first, so both boards have a card to open. `section: 1` is the tab
  // `MyDeals` opens on; `seedBoughtDeal` lands on the BRRRR pipeline's first
  // stage, which is the tab `BoughtDeals` opens on.
  const activeDeal = await seed.seedActiveDeal('BRRRR', { section: 1 });
  const boughtDeal = await seed.seedBoughtDeal('BRRRR');

  // --- / --------------------------------------------------------------------
  await page.goto('/');
  await expect(page.getByTestId('landing.offer')).toBeVisible();
  await quietAfter('/ (landing)');

  // --- /analyze -------------------------------------------------------------
  await page.goto('/analyze');
  await expect(page.getByTestId('form.root')).toBeVisible();
  await quietAfter('/analyze (route)');

  // The three fields `validateDealInputs` requires of a BRRRR deal; every
  // other bound is already satisfied by `createEmptyDealForm`'s defaults. The
  // point is to reach the save modal, not to save, so typing the other twenty
  // fields would only make the check slower and no stricter.
  await fillForm(page, ['purchasePrice', 'arv_in_thousands', 'rent'], BRRRR_PAYLOAD);
  await page.getByTestId('analyze.analyze-save').click();
  await expect(page.getByTestId('analyze.modal')).toBeVisible();
  await quietAfter('/analyze save modal open');

  // Closes are asserted the other way round on purpose: `quietAfter` reads the
  // timeline *before* it advances the clock, so it catches the leave tween
  // mid-flight, and the second it then grants is what both finishes that tween
  // and lets Vue take the node out. `toBeHidden` after it is the proof the
  // leave actually completed rather than stalling with the overlay still up.
  await page.getByTestId('analyze.modal.cancel').click();
  await quietAfter('/analyze save modal cancelled');
  await expect(page.getByTestId('analyze.modal')).toBeHidden();

  // --- /my-deals ------------------------------------------------------------
  await page.goto('/my-deals');
  await expect(page.getByTestId(`mydeals.card.${activeDeal.id}`)).toBeVisible();
  await quietAfter('/my-deals (route)');

  await page.getByTestId(`mydeals.card.${activeDeal.id}`).click();
  await expect(page.getByTestId('mydeals.modal')).toBeVisible();
  // The modal re-analyzes on a 500 ms debounce and reveals the tiles when the
  // answer arrives. Waiting for the panel here is what keeps the assertion
  // below from racing that reveal.
  await settle(600);
  await expect(page.getByTestId('mydeals.modal.results')).toBeVisible();
  await quietAfter('/my-deals deal modal open');

  await page.getByTestId('mydeals.modal.footer-close').click();
  await quietAfter('/my-deals deal modal closed');
  await expect(page.getByTestId('mydeals.modal')).toBeHidden();

  // --- /bought-deals --------------------------------------------------------
  await page.goto('/bought-deals');
  await expect(page.getByTestId(`boughtdeals.card.${boughtDeal.id}`)).toBeVisible();
  await quietAfter('/bought-deals (route)');

  await page.getByTestId(`boughtdeals.card.${boughtDeal.id}`).click();
  await expect(page.getByTestId('boughtdeals.modal')).toBeVisible();
  await settle(600);
  await expect(page.getByTestId('boughtdeals.modal.results')).toBeVisible();
  await quietAfter('/bought-deals deal modal open');

  await page.getByTestId('boughtdeals.modal.close').click();
  await quietAfter('/bought-deals deal modal closed');
  await expect(page.getByTestId('boughtdeals.modal')).toBeHidden();

  // --- /liquidity -----------------------------------------------------------
  await page.goto('/liquidity');
  await expect(page.getByTestId('liquidity.add-flow')).toBeVisible();
  await quietAfter('/liquidity (route)');

  await page.getByTestId('liquidity.settings-open').click();
  await expect(page.getByTestId('settings.root')).toBeVisible();
  await quietAfter('/liquidity settings modal open');

  // `SettingsPanel` is the one modal still on a CSS `<Transition>` rather than
  // a preset, and a CSS leave needs the clock too: Vue swaps `leave-from` for
  // `leave-to` inside a `requestAnimationFrame`, which a paused clock never
  // reaches. `quietAfter` runs the clock forward, and only then can the node go.
  await page.getByTestId('settings.cancel').click();
  await quietAfter('/liquidity settings modal closed');
  await expect(page.getByTestId('settings.root')).toBeHidden();

  // --- /reps ----------------------------------------------------------------
  await page.goto('/reps');
  await expect(page.getByTestId('reps.people-toggle')).toBeVisible();
  await quietAfter('/reps (route)');

  // A walk in which nothing ever animated would satisfy every assertion above
  // while proving nothing at all, so the totals are an assertion too.
  const observed = readings.reduce((total, reading) => total + reading.running, 0);
  expect(observed, 'the walk saw at least one tween actually running').toBeGreaterThan(0);

  console.log(
    ['', 'no-live-tweens — tweens running / left after 1 s:']
      .concat(
        readings.map(
          (reading) =>
            `  ${String(reading.running).padStart(2)} / ${reading.quiet}  ${reading.step}`,
        ),
      )
      .join('\n'),
  );
});
