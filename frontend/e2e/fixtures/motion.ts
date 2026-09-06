import { expect, type Page } from '@playwright/test';

/**
 * Motion guards.
 *
 * Two things the overhaul must not break, checked here so the check exists
 * *before* any animation library lands:
 *
 *  - Nothing is left tweening once an interaction settles. GSAP is not
 *    installed today, so this passes trivially — that is the point: the
 *    assertion is already in place for the phase that introduces it.
 *  - An overlay that claims the viewport actually covers it, both the instant
 *    it appears and after any entrance animation would have finished. A modal
 *    that animates in from 90% scale leaves a live gap at the edges, and on a
 *    phone that gap is where the user's thumb lands.
 */

declare global {
  interface Window {
    gsap?: { globalTimeline: { getChildren(): unknown[] } };
  }
}

export async function expectNoLiveTweens(page: Page): Promise<void> {
  const quiet = await page.evaluate(
    () => !window.gsap || window.gsap.globalTimeline.getChildren().length === 0,
  );
  expect(quiet, 'expected no live GSAP tweens').toBe(true);
}

async function overlayBox(page: Page, testId: string) {
  return page.evaluate((id) => {
    const element = document.querySelector(`[data-testid="${id}"]`);
    if (!element) return null;
    const rect = element.getBoundingClientRect();
    return {
      top: rect.top,
      left: rect.left,
      width: rect.width,
      height: rect.height,
      viewportWidth: window.innerWidth,
      viewportHeight: window.innerHeight,
    };
  }, testId);
}

/**
 * The overlay fills the viewport (±1 px) both 50 ms and 500 ms after it
 * appears — early enough to catch an entrance animation that starts small,
 * late enough to catch one that never finishes.
 */
export async function expectOverlayFillsViewport(
  page: Page,
  testId: string,
): Promise<void> {
  for (const [label, advanceMs] of [
    ['50ms after appearance', 50],
    ['500ms after appearance', 450],
  ] as const) {
    await page.clock.runFor(advanceMs);
    const box = await overlayBox(page, testId);
    expect(box, `${testId} present ${label}`).not.toBeNull();
    expect(Math.abs(box!.left), `${testId} left ${label}`).toBeLessThanOrEqual(1);
    expect(Math.abs(box!.top), `${testId} top ${label}`).toBeLessThanOrEqual(1);
    expect(
      Math.abs(box!.width - box!.viewportWidth),
      `${testId} width ${label}`,
    ).toBeLessThanOrEqual(1);
    expect(
      Math.abs(box!.height - box!.viewportHeight),
      `${testId} height ${label}`,
    ).toBeLessThanOrEqual(1);
  }
}
